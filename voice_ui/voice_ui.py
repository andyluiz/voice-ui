import logging
import queue
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Optional

from .config import VoiceUIConfig
from .speech_detection.speech_detector import (
    HotwordDetectedEvent,
    MetaDataEvent,
    PartialSpeechEndedEvent,
    SpeechDetector,
    SpeechEndedEvent,
    SpeechEvent,
    SpeechStartedEvent,
    WaitingForHotwordEvent,
)
from .speech_recognition import SpeechToTextTranscriber, TranscriberFactory
from .speech_synthesis import TextToSpeechAudioStreamer, TTSFactory

logger = logging.getLogger(__name__)


class PartialTranscriptionEvent(SpeechEvent):
    pass


class TranscriptionEvent(SpeechEvent):
    pass


class VoiceUI:
    def __init__(
        self,
        speech_callback: Callable[[SpeechEvent], bool],
        config: Optional[VoiceUIConfig] = None,
    ):
        self._config = config if config else VoiceUIConfig()
        self._terminated = True
        self._speech_callback = speech_callback

        # Voice input
        self._speech_events = queue.Queue()
        self._speech_detector = SpeechDetector(
            on_speech_event=lambda event: self._speech_events.put(event),
            speaker_profiles_dir=self._config.voice_profiles_dir,
            threshold=self._config.vad_threshold,
            pre_speech_duration=self._config.pre_speech_duration,  # One second will include the hotword detected. Anything less that 0.75 will truncate it.
            post_speech_duration=self._config.post_speech_duration,
            max_speech_duration=self._config.max_speech_duration,
            additional_keyword_paths=self._config.additional_keyword_paths,
            vad_engine=self._config.vad_engine,
        )
        self._speech_event_handler_thread = None

        # Voice transcriber
        self._audio_transcriber: SpeechToTextTranscriber = TranscriberFactory.create(
            self._config.audio_transcriber
        )

        # Voice output
        self._speaker_queue = queue.Queue()
        self._tts_streamer: TextToSpeechAudioStreamer = TTSFactory.create(
            self._config.tts_engine
        )

    def _speech_event_handler(self):
        """
        This method listens for speech events and handles the transcription of audio data into text.

        It uses the WhisperTranscriber to convert the audio data into text. The method continuously listens for speech
        events from the speech detector and processes them accordingly.

        If no speech event is received for 30 seconds, it stops the speech detector, calls the speech callback to
        indicate waiting for the hotword, detects the hotword, and starts the speech detector again.

        When speech is detected, it stops the TTS stream and calls the speech callback with the appropriate event.
        When partial or complete speech is received, it transcribes the audio data into text using the WhisperTranscriber
        and calls the speech callback with the transcribed text and speaker information.

        The method runs until the `_terminated` flag is set.
        """
        user_input = ""
        self._last_speech_event_at = datetime.now()

        def safe_callback_call(*args, **kwargs):
            """
            Helper function to safely call the speech callback, catching and logging any exceptions.
            """
            try:
                self._speech_callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in speech callback: {str(e)}")

        # Keep listening until an utterance is detected
        while not self._terminated:
            try:
                # Wait for the next speech event from the queue
                event = self._speech_events.get(timeout=1)

                if isinstance(event, MetaDataEvent):
                    continue

                self._last_speech_event_at = datetime.now()
            except queue.Empty:
                # If no speech event is received within 1 second
                now = datetime.now()
                if self.is_speaking():
                    logger.debug("Still speaking, update last speech event timestamp.")
                    # If the TTS is currently speaking, update the last speech event time
                    self._last_speech_event_at = now
                    continue

                # Handle inactivity
                hotword_inactivity_timeout = self._config.hotword_inactivity_timeout

                # If the hotword inactivity timeout is not set or not a valid number, skip
                if hotword_inactivity_timeout is None or not isinstance(
                    hotword_inactivity_timeout, (float, int)
                ):
                    continue

                # If already in hotword detection mode, skip
                if (
                    self._speech_detector.detection_mode
                    == SpeechDetector.DetectionMode.HOTWORD
                ):
                    continue

                # If the hotword inactivity timeout has not been reached, skip
                if (now - self._last_speech_event_at) < timedelta(
                    seconds=hotword_inactivity_timeout
                ):
                    continue

                logger.info("Inactivity detected. Waiting for hotword.")

                # Set the detection mode to hotword
                self._speech_detector.set_detection_mode(
                    SpeechDetector.DetectionMode.HOTWORD
                )

                # Call the speech callback to indicate waiting for hotword
                safe_callback_call(event=WaitingForHotwordEvent())
                user_input = ""

                continue

            if not isinstance(
                event,
                (
                    SpeechStartedEvent,
                    PartialSpeechEndedEvent,
                    SpeechEndedEvent,
                    HotwordDetectedEvent,
                    WaitingForHotwordEvent,
                ),
            ):
                logger.debug(f"Speech event: {event}")
                continue

            if isinstance(event, WaitingForHotwordEvent):
                logger.info("Waiting for hotword.")

                # Call the speech callback to indicate waiting for hotword
                safe_callback_call(event=event)
                user_input = ""

            if isinstance(event, HotwordDetectedEvent):
                logger.info("Hotword detected.")

                # self._speech_detector.set_detection_mode(SpeechDetector.DetectionMode.VOICE_ACTIVITY)

                # Call the speech callback to indicate hotword detected
                safe_callback_call(event=event)

            if isinstance(event, SpeechStartedEvent):
                logger.info("Speech detected. Stopping TTS stream.")
                self.stop_speaking()

                safe_callback_call(event=event)

            if isinstance(event, (PartialSpeechEndedEvent, SpeechEndedEvent)):
                # Call the speech callback
                safe_callback_call(event=event)

                # Update the user role name
                audio_data = event.get("audio_data")
                if audio_data is None:
                    logger.error(f"No audio data for event {event}")
                    continue

                metadata = event.get("metadata")
                speaker = ((metadata and metadata["speaker"]) or {}).get("name", "user")

                if self._audio_transcriber is not None:
                    try:
                        # Convert speech to text
                        response = self._audio_transcriber.transcribe(
                            audio_data=audio_data, prompt=user_input
                        )
                        user_input += " " + response
                        user_input = user_input.strip()
                    except Exception as e:
                        logger.error(f"Error transcribing audio: {e}")
                        continue

                    # Call the speech callback
                    safe_callback_call(
                        event=PartialTranscriptionEvent(
                            text=response,
                            speaker=speaker,
                            speech_id=event.id,
                        )
                    )

                    # Call the speech callback
                    if isinstance(event, SpeechEndedEvent) and len(user_input) > 0:
                        safe_callback_call(
                            event=TranscriptionEvent(
                                text=user_input,
                                speaker=speaker,
                                speech_id=event.id,
                            )
                        )
                        user_input = ""

                    logger.info(f'Utterance: "{user_input}"')

    def start(self):
        if not self._terminated:
            return

        self._terminated = False

        self._tts_thread = threading.Thread(
            target=self._text_to_speech_thread_function,
            daemon=True,
            name="TextToSpeechThread",
        )
        self._tts_thread.start()

        self._speech_event_handler_thread = threading.Thread(
            target=self._speech_event_handler,
            daemon=True,
            name="SpeechEventHandlerThread",
        )
        self._speech_event_handler_thread.start()

        self._speech_detector.start()

    def terminate(self, timeout: Optional[float] = None):
        if self._terminated:
            return

        self._terminated = True

        # Stop the speech detector and TTS streamer
        self._speech_detector.stop()
        self._tts_streamer.terminate()

        # Wait for the threads to finish
        try:
            self._speech_events.put(MetaDataEvent())
            self._speech_event_handler_thread.join(timeout=timeout)
        finally:
            self._speech_event_handler_thread = None

        try:
            self._tts_thread.join(timeout=timeout)
        finally:
            self._tts_thread = None

    def stop_listening(self):
        # Set the date to zero seconds after epoch
        self._last_speech_event_at = datetime.fromtimestamp(0)

    def resume(self):
        pass

    # Text-to-Speech methods
    def _text_to_speech_thread_function(self):
        while not self._terminated:
            try:
                text = self._speaker_queue.get(timeout=1)

                # if not self._voice_output_enabled:
                #     continue

                self._tts_streamer.speak(
                    text=text,
                    voice=self._config.voice_name,
                )
                self._speaker_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error while transcribing text: {e}")

    def speak(self, text: str, wait: bool = False):
        if wait:
            self._tts_streamer.speak(
                text=text,
                voice=self._config.voice_name,
            )
            while self._tts_streamer.is_speaking():
                time.sleep(timedelta(milliseconds=10).total_seconds())
        else:
            self._speaker_queue.put(text)

    def is_speaking(self) -> bool:
        return self._speaker_queue.qsize() > 0 or self._tts_streamer.is_speaking()

    def stop_speaking(self):
        logger.debug("Cleaning output speech queue")
        self._tts_streamer.stop()

        while True:
            try:
                self._speaker_queue.get_nowait()
                self._speaker_queue.task_done()
            except queue.Empty:
                break

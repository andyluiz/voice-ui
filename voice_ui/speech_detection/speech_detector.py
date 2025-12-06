import logging
import threading
from abc import ABC
from enum import Enum, auto, unique
from pathlib import Path
from typing import Callable, Optional
from uuid import UUID, uuid4

from ..audio_io.audio_data import AudioData
from .speaker_profile_manager import SpeakerProfileManager
from .vad_microphone import MicrophoneVADStream

logger = logging.getLogger(__name__)


class SpeechEvent(ABC):
    def __init__(self, **kwargs):
        if self.__class__ == SpeechEvent:
            raise TypeError('SpeechEvent is an abstract class and cannot be instantiated directly')

        self._id = uuid4()

        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)
            else:
                raise AttributeError(f'{self.__class__.__name__} already has attribute {k}')

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def id(self) -> UUID:
        return self._id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return (self.__dict__ == other.__dict__)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.__dict__})'

    def get(self, key: str, default=None):
        return self.__dict__.get(key, default)

    def __getitem__(self, key: str):
        return self.__dict__[key]

    def __iter__(self):
        return iter(self.__dict__.items())

    # def __getattr__(self, key):
    #     if key in self._data:
    #         return self._data[key]
    #     raise AttributeError(f'{self.__class__.__name__} has no attribute {key}')


class MetaDataEvent(SpeechEvent):
    pass


class SpeechStartedEvent(SpeechEvent):
    pass


class PartialSpeechEndedEvent(SpeechEvent):
    pass


class SpeechEndedEvent(SpeechEvent):
    pass


class WaitingForHotwordEvent(SpeechEvent):
    pass


class HotwordDetectedEvent(SpeechEvent):
    pass


class SpeechDetector:
    @unique
    class DetectionMode(Enum):
        HOTWORD = auto()
        VOICE_ACTIVITY = auto()

    def __init__(
        self,
        on_speech_event: Callable[[SpeechEvent], None],
        speaker_profiles_dir: Optional[Path] = None,
        threshold: Optional[float] = None,
        pre_speech_duration: Optional[float] = None,  # Duration in seconds before speech is considered to have started
        post_speech_duration: Optional[float] = None,  # Duration in seconds after speech is considered to have ended
        max_speech_duration: Optional[float] = None,  # Maximum duration in seconds of speech to be considered
        **kwargs,
    ):
        """
        Initialize a SpeechDetector instance.

        The SpeechDetector coordinates voice activity detection (VAD) with optional hotword detection
        and speaker profiling to identify speech events in audio streams.

        Args:
            on_speech_event: Callback function invoked when speech events occur. Receives a SpeechEvent
                instance (e.g., SpeechStartedEvent, SpeechEndedEvent, HotwordDetectedEvent).
                **Important**: This callback is invoked by the internal speech processing thread and must
                not block for extended periods, as doing so may cause event delays or missed detections.
            speaker_profiles_dir: Optional path to a directory containing speaker profile files for
                speaker identification. If provided, speaker detection will be enabled during speech.
                Defaults to None (speaker detection disabled).
            threshold: Optional VAD sensitivity threshold. Passed to MicrophoneVADStream.
                Defaults to None (uses VAD engine defaults).
            pre_speech_duration: Optional duration in seconds of audio to prepend to detected speech.
                Helps capture speech that begins just before VAD triggers. Defaults to None.
            post_speech_duration: Optional duration in seconds of silence to append after detected speech.
                Helps capture trailing speech before silence is detected. Defaults to None.
            max_speech_duration: Maximum duration in seconds for a single continuous speech segment.
                If exceeded, a PartialSpeechEndedEvent is emitted and collection resets. Defaults to 10 seconds.
            **kwargs: Additional arguments passed to MicrophoneVADStream (e.g., vad_engine, hotword_engine).

        Raises:
            ValueError: Raised in _run() if on_speech_event callback is None when the detector starts.
        """
        # Set defaults
        if max_speech_duration is None:
            max_speech_duration = 10

        self._source_stream = MicrophoneVADStream(
            threshold=threshold,
            pre_speech_duration=pre_speech_duration,
            post_speech_duration=post_speech_duration,
            **kwargs,
        )

        self._on_speech_event = on_speech_event
        self._max_speech_duration = max_speech_duration

        self._speaker_profiles_dir = speaker_profiles_dir
        self._profile_manager = SpeakerProfileManager(self._speaker_profiles_dir) if self._speaker_profiles_dir else None
        self._thread = None

    def start(self):
        if self._profile_manager:
            self._profile_manager.load_profiles()

        self._thread = threading.Thread(target=self._run, daemon=True, name='SpeechDetectorThread')
        self._thread.start()

    def stop(self):
        self._source_stream.pause()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self._profile_manager = None

    @property
    def detection_mode(self):
        mapping = {
            MicrophoneVADStream.DetectionMode.HOTWORD: SpeechDetector.DetectionMode.HOTWORD,
            MicrophoneVADStream.DetectionMode.VOICE_ACTIVITY: SpeechDetector.DetectionMode.VOICE_ACTIVITY,
        }
        return mapping[self._source_stream.detection_mode]

    def set_detection_mode(self, mode: DetectionMode):
        mapping = {
            SpeechDetector.DetectionMode.HOTWORD: MicrophoneVADStream.DetectionMode.HOTWORD,
            SpeechDetector.DetectionMode.VOICE_ACTIVITY: MicrophoneVADStream.DetectionMode.VOICE_ACTIVITY,
        }
        self._source_stream.set_detection_mode(mapping[mode])

    def _run(self):
        logger.debug('Speech detector thread started')

        if self._on_speech_event is None:
            raise ValueError("Callback is required")

        # Calculate chunk durations
        max_chunks = self._source_stream.convert_duration_to_chunks(self._max_speech_duration)
        logger.debug(f"Max chunks: {max_chunks}")

        # Initialize counters and flags
        self.collected_chunks = []
        self.speaker_scores = []

        # Resume audio stream
        self._source_stream.resume()

        # Main loop to process audio chunks
        try:
            speech_detected = False
            waiting_for_hotword = False

            for chunk in self._source_stream.generator():
                if len(chunk) == 0:
                    speech_detected = False
                    self._handle_speech_end()

                    waiting_for_hotword = (self._source_stream.detection_mode == MicrophoneVADStream.DetectionMode.HOTWORD)
                    if waiting_for_hotword:
                        self._handle_hotword_waiting()

                    continue

                # Detect speaker
                if self._profile_manager:
                    audio_frame = self._source_stream.convert_data(chunk)

                    scores = self._profile_manager.detect_speaker(audio_frame)
                    if scores:
                        self.speaker_scores.append(scores)
                        logger.debug(f"Scores: {scores}, speaker ID: {self._profile_manager.get_speaker_name(scores)}")

                # Check if we're waiting for a hotword
                if waiting_for_hotword:
                    self._handle_hotword_detection()
                    waiting_for_hotword = False

                # Detect start of speech
                if not speech_detected:
                    speech_detected = True
                    self._handle_speech_start()

                # Collect chunks during speech detection
                self.collected_chunks.append(chunk)

                # Handle case where collected chunks exceed max duration
                self._handle_collected_chunks_overflow(max_chunks)

            # Handle case where stream was closed before end of the speech
            if speech_detected:
                self._handle_speech_end()

        finally:
            # Pause audio processing when closed
            self._source_stream.pause()

            del self.collected_chunks

        logger.debug('Speech detector thread finished')

    def _handle_hotword_waiting(self):
        """
        Handle hotword waiting.
        """
        logger.debug("Waiting for hotword")

        self._on_speech_event(
            event=WaitingForHotwordEvent(
                hotwords=self._source_stream.available_keywords,
            )
        )

    def _handle_hotword_detection(self):
        """
        Handle hotword detection.
        """
        logger.debug("Hotword detected")

        # Find the speaker
        speaker_info = None
        if self._profile_manager:
            # # Calculate the average scores for each speaker
            # scores = [sum(score) / len(score) for score in zip(*self.speaker_scores)]
            # Calculate the total scores for each speaker
            scores = [sum(score) for score in zip(*self.speaker_scores)]

            # Get the speaker with the highest score
            speaker_info = self._profile_manager.get_speaker_name(scores)
            logger.debug(f"Speaker is {speaker_info} with scores {scores}")

        self._on_speech_event(
            event=HotwordDetectedEvent(
                hotword_detected=self._source_stream.last_hotword_detected,
                speaker=speaker_info,
            )
        )

    def _handle_speech_start(self):
        """
        Handle the start of speech detection.
        """
        logger.debug("Speech start detected")

        self._on_speech_event(event=SpeechStartedEvent())

    def _handle_speech_end(self):
        """
        Handle the end of speech detection.
        """
        logger.debug("Speech end detected")

        # Find the speaker
        speaker_info = None
        if self._profile_manager:
            # # Calculate the average scores for each speaker
            # scores = [sum(score) / len(score) for score in zip(*self.speaker_scores)]
            # Calculate the total scores for each speaker
            scores = [sum(score) for score in zip(*self.speaker_scores)]

            # Get the speaker with the highest score
            speaker_info = self._profile_manager.get_speaker_name(scores)
            logger.debug(f"Speaker is {speaker_info} with scores {scores}")

        self._on_speech_event(
            event=SpeechEndedEvent(
                audio_data=AudioData(
                    channels=self._source_stream.channels,
                    sample_size=self._source_stream.sample_size,
                    rate=self._source_stream.rate,
                    content=b"".join(self.collected_chunks),
                ),
                metadata={
                    "speaker": speaker_info,
                }
            )
        )
        self.collected_chunks.clear()
        self.speaker_scores.clear()

    def _handle_collected_chunks_overflow(self, max_chunks):
        """
        Handle the case where collected chunks exceed the maximum duration.
        """
        n_collected_chunks = len(self.collected_chunks)
        if n_collected_chunks > int(0.8 * max_chunks) or n_collected_chunks > int(1.2 * max_chunks):
            # Find the speaker
            speaker_info = None
            if self._profile_manager:
                # # Calculate the average scores for each speaker
                # scores = [sum(score) / len(score) for score in zip(*self.speaker_scores)]
                # Calculate the total scores for each speaker
                scores = [sum(score) for score in zip(*self.speaker_scores)]

                # Get the speaker with the highest score
                speaker_info = self._profile_manager.get_speaker_name(scores)
                logger.debug(f"Speaker is {speaker_info} with scores {scores}")

            self._on_speech_event(
                event=PartialSpeechEndedEvent(
                    audio_data=AudioData(
                        channels=self._source_stream.channels,
                        sample_size=self._source_stream.sample_size,
                        rate=self._source_stream.rate,
                        content=b"".join(self.collected_chunks),
                    ),
                    metadata={
                        "speaker": speaker_info,
                    }
                )
            )
            self.collected_chunks.clear()
            self.speaker_scores.clear()

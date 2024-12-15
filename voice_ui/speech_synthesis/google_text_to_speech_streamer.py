import itertools
import logging
import queue
import threading
from typing import Dict, List, Optional

from google.cloud import texttospeech

from ..audio_io.player import Player
from .text_to_speech_streamer import TextToSpeechAudioStreamer


class GoogleTextToSpeechAudioStreamer(TextToSpeechAudioStreamer):
    def __init__(self):
        self._stopped = False
        self._speaking = False
        self._lock = threading.Lock()

        self._terminated = False
        self._speaker_thread = threading.Thread(
            target=self._speaker_thread_function,
            daemon=True
        )

        self._client = texttospeech.TextToSpeechClient()
        self._player = Player()
        self._audio_bytes_queue = queue.Queue()

        self._speaker_thread.start()

    @staticmethod
    def name() -> str:
        return "google"

    def __del__(self):
        self.stop()
        self._terminated = True
        if self._speaker_thread.is_alive():
            self._speaker_thread.join(timeout=5)

    def _speaker_thread_function(self):
        self._terminated = False

        while not self._terminated:
            try:
                audio_data = self._audio_bytes_queue.get(timeout=1)

                if self.is_stopped():
                    continue

                # logging.debug(f'Playing {len(audio_data)} bytes of audio data')
                self._speaking = True
                self._player.play_data(audio_data)
                self._speaking = False

            except queue.Empty:
                continue
            except Exception as e:
                self._speaking = False
                logging.error(f'Error while playing audio: {e}')

    def stop(self):
        with self._lock:
            self._stopped = True

    def is_stopped(self):
        with self._lock:
            return self._stopped

    def is_speaking(self):
        return self._speaking

    def available_voices(self) -> List[Dict]:
        return self._client.list_voices()

    def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs,
    ):
        # Reset the stopped flag
        with self._lock:
            self._stopped = False

        logging.debug(f'Transcribing text: "{text}"')

        try:
            # See https://cloud.google.com/text-to-speech/docs/voices for all voices.
            voice_selection_params = texttospeech.VoiceSelectionParams(
                name=voice if voice else "en-US-Journey-D",
                language_code=kwargs.get('language_code', "en-US"),
            )

            streaming_config = texttospeech.StreamingSynthesizeConfig(
                voice=voice_selection_params
            )

            # Set the config for your stream. The first request must contain your config, and then each subsequent request must contain text.
            config_request = texttospeech.StreamingSynthesizeRequest(
                streaming_config=streaming_config
            )

            streaming_responses = self._client.streaming_synthesize(
                requests=itertools.chain(
                    [config_request],
                    [
                        texttospeech.StreamingSynthesizeRequest(
                            input=texttospeech.StreamingSynthesisInput(text=text)
                        )
                    ]
                )
            )

            for response in streaming_responses:
                if self.is_stopped():
                    logging.debug('Stream is stopped. Leaving.')
                    break

                self._audio_bytes_queue.put(response.audio_content)

        except Exception as e:
            self._speaking = False
            logging.error(f'Error while playing audio: {e}')

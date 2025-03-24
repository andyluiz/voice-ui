import itertools
import logging
import queue
from typing import Dict, List, Optional

from google.api_core import exceptions
from google.cloud import texttospeech

from .pass_through_text_to_speech_streamer import PassThroughTextToSpeechAudioStreamer

logger = logging.getLogger(__name__)


class GoogleTextToSpeechAudioStreamer(PassThroughTextToSpeechAudioStreamer):
    def __init__(self):
        self._client = texttospeech.TextToSpeechClient()
        self._input_timeout = 3

        super().__init__()

    @staticmethod
    def name() -> str:
        return "google"

    def available_voices(self, language_code: Optional[str] = None) -> List[Dict]:
        return self._client.list_voices(language_code=language_code)

    def _synthesize_request_generator(self, starting_text: str):
        yield texttospeech.StreamingSynthesizeRequest(
            input=texttospeech.StreamingSynthesisInput(text=starting_text)
        )

        while not self._terminated:
            try:
                (text, _, _) = self._data_queue.get(timeout=self._input_timeout)  # Google streaming TTS has a 5 second timeout on its input. This timeout has to be less than that.
            except queue.Empty:
                logger.debug('No more text to synthesize')
                return

            logger.debug(f'Transcribing text: "{text}"')

            yield texttospeech.StreamingSynthesizeRequest(
                input=texttospeech.StreamingSynthesisInput(text=text)
            )

    def _speaker_thread_function(self):
        logger.debug('Starting TTS thread')
        while not self._terminated:
            try:
                (text, voice, kwargs) = self._data_queue.get(timeout=self._input_timeout)
            except queue.Empty:
                continue

            try:
                logger.debug(f'Transcribing text: "{text}"')

                self._speaking = True

                # Set the config for your stream. The first request must contain your config, and then each subsequent request must contain text.
                config_request = texttospeech.StreamingSynthesizeRequest(
                    streaming_config=texttospeech.StreamingSynthesizeConfig(
                        # See https://cloud.google.com/text-to-speech/docs/voices for all voices.
                        voice=texttospeech.VoiceSelectionParams(
                            language_code=(kwargs or {}).get('language_code', "en-US"),
                            name=voice if voice else "en-US-Journey-D",
                        )
                    )
                )

                streaming_responses = self._client.streaming_synthesize(
                    requests=itertools.chain(
                        [config_request],
                        self._synthesize_request_generator(starting_text=text)
                    )
                )

                for response in streaming_responses:
                    if self.is_stopped():
                        logger.debug('Stream is stopped. Leaving.')
                        break

                    self._player.play_data(response.audio_content)

                self._speaking = False

            except exceptions.GoogleAPIError as e:
                logger.error(f'Google API error: {e}')

            except Exception as e:
                logger.error(f'Error while playing audio: {e}')

            finally:
                self._speaking = False

        logger.debug('TTS thread finished')

    def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs,
    ):
        # Reset the stopped flag
        with self._lock:
            self._stopped = False

        logger.debug(f'Speaking text: "{text}"')
        self._data_queue.put((text.strip(), voice, kwargs))

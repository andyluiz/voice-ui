import itertools
import logging
import queue
import threading
from typing import Dict, List, Optional

from google.cloud import texttospeech

from .pass_through_text_to_speech_streamer import PassThroughTextToSpeechAudioStreamer


class GoogleTextToSpeechAudioStreamer(PassThroughTextToSpeechAudioStreamer):
    def __init__(self):
        self._client = texttospeech.TextToSpeechClient()

        super().__init__()

    @staticmethod
    def name() -> str:
        return "google"

    def available_voices(self) -> List[Dict]:
        return self._client.list_voices()

    def _synthesize_request_generator(self):
        while not self._terminated:
            try:
                text = self._data_queue.get(timeout=1)

                text = text.strip()

                logging.debug(f'Transcribing text: "{text}"')

                yield texttospeech.StreamingSynthesizeRequest(
                    input=texttospeech.StreamingSynthesisInput(text=text)
                )

                self._data_queue.task_done()
            except queue.Empty:
                logging.debug('No more text to synthesize')
                return

        logging.debug('Done synthesizing')

    def _speaker_thread_function(self, voice: Optional[str] = None, **kwargs):
        logging.debug('Starting TTS thread')
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
                    self._synthesize_request_generator()
                )
            )

            self._speaking = True

            for response in streaming_responses:
                if self.is_stopped():
                    logging.debug('Stream is stopped. Leaving.')
                    break

                self._player.play_data(response.audio_content)

            self._speaking = False
            logging.debug('TTS thread finished')

        except Exception as e:
            logging.error(f'Error while playing audio: {e}')

        finally:
            self._speaking = False
            # Clear the queue
            while True:
                try:
                    self._data_queue.get_nowait()
                    self._data_queue.task_done()
                except queue.Empty:
                    break

    def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs,
    ):
        # Reset the stopped flag
        with self._lock:
            self._stopped = False

        logging.debug(f'Speaking text: "{text}"')
        self._data_queue.put(text)

        if not self._speaker_thread.is_alive():
            logging.debug('Starting new TTS thread')
            if self._speaker_thread:
                self._speaker_thread.join()

            self._speaker_thread = threading.Thread(
                target=self._speaker_thread_function,
                kwargs={
                    'voice': voice,
                    **kwargs,
                }
            )
            self._speaker_thread.start()

        self._data_queue.join()

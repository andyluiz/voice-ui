import logging
import os
import wave
from enum import StrEnum, unique
from typing import Dict, List, Optional

import requests

from .pass_through_text_to_speech_streamer import PassThroughTextToSpeechAudioStreamer


class OpenAITextToSpeechAudioStreamer(PassThroughTextToSpeechAudioStreamer):
    @unique
    class Voice(StrEnum):
        ALLOY = 'alloy'
        ECHO = 'echo'
        FABLE = 'fable'
        ONYX = 'onyx'
        NOVA = 'nova'
        SHIMMER = 'shimmer'

    @staticmethod
    def name():
        return "openai-tts"

    def available_voices(self) -> List[Dict]:
        return [
            {
                'name': self.Voice.ALLOY,
                'gender': 'NEUTRAL',
            },
            {
                'name': self.Voice.ECHO,
                'gender': 'MALE',
            },
            {
                'name': self.Voice.FABLE,
                'gender': 'NEUTRAL',
            },
            {
                'name': self.Voice.ONYX,
                'gender': 'MALE',
            },
            {
                'name': self.Voice.NOVA,
                'gender': 'FEMALE',
            },
            {
                'name': self.Voice.SHIMMER,
                'gender': 'FEMALE',
            },
        ]

    def speak(
        self,
        text: str,
        voice: Optional[Voice] = None,
        **kwargs,
    ):
        # Reset the stopped flag
        with self._lock:
            self._stopped = False

        logging.debug(f'Transcribing text: "{text}"')

        logging.debug('Making the API request')

        for i in range(2):
            try:
                # Send the request to the OpenAI API
                response = requests.post(
                    'https://api.openai.com/v1/audio/speech',
                    headers={
                        'Authorization': f'Bearer {os.environ["OPENAI_API_KEY"]}',
                        'Content-Type': 'application/json; charset=utf-8',
                    },
                    json={
                        "model": "tts-1",
                        "input": text,
                        "voice": str(voice if voice else self.Voice.SHIMMER),
                        "response_format": "wav",
                        **kwargs,
                    },
                    stream=True,
                )

                logging.debug('API Response received')

                response.raise_for_status()

                # Stream the content
                logging.debug('Reading chunks from API response')
                num_chunks = 0
                buffer_underrun_protection_enabled = True
                with wave.open(response.raw, 'rb') as wf:
                    while (data := wf.readframes(4096 if buffer_underrun_protection_enabled else 1024)):
                        if self.is_stopped():
                            logging.debug('Stream is stopped. Leaving.')
                            break
                        num_chunks += len(data)
                        self._data_queue.put(data)
                        buffer_underrun_protection_enabled = False
                logging.debug(f'Done reading {num_chunks} chunks from API response')

                break

            except requests.exceptions.HTTPError as e:
                logging.error(f'Error: {e}')
                logging.debug(f'Response headers: {response.headers}')
                logging.debug(f'Response message: {response.json()}')
                continue

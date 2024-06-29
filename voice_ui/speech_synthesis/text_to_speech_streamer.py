import logging
import os
import queue
import threading
import wave
from enum import StrEnum, unique
from typing import Dict, List, Optional

import requests

from .player import Player


class TextToSpeechAudioStreamer:
    @unique
    class Voice(StrEnum):
        ALLOY = 'alloy'
        ECHO = 'echo'
        FABLE = 'fable'
        ONYX = 'onyx'
        NOVA = 'nova'
        SHIMMER = 'shimmer'

    def __init__(self):
        self._stopped = False
        self._speaking = False
        self._lock = threading.Lock()

        self._audio_bytes_queue = queue.Queue()
        self._terminated = False
        self._speaker_thread = threading.Thread(target=self._speaker, daemon=True)
        self._speaker_thread.start()

    def __del__(self):
        self.stop()
        self._terminated = True
        self._speaker_thread.join(timeout=5)

    def stop(self):
        with self._lock:
            self._stopped = True

    def is_stopped(self):
        with self._lock:
            return self._stopped

    def is_speaking(self):
        return self._speaking

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

    def transcribe_to_stream(
        self,
        text: str,
        stream: queue.Queue,
        voice: Optional[Voice] = None,
        response_format: str = None,  # ignored
        **kwargs,
    ):
        # Reset the stopped flag
        with self._lock:
            self._stopped = False

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
                with wave.open(response.raw, 'rb') as wf:
                    while (data := wf.readframes(1024)):
                        if self.is_stopped():
                            logging.debug('Stream is stopped. Leaving.')
                            break
                        num_chunks += len(data)
                        stream.put(data)
                logging.debug(f'Done reading {num_chunks} chunks from API response')

                break

            except requests.exceptions.HTTPError as e:
                logging.error(f'Error: {e}')
                logging.debug(f'Response headers: {response.headers}')
                logging.debug(f'Response message: {response.json()}')
                continue

    def _speaker(self):
        player = Player()
        while not self._terminated:
            try:
                audio_data = self._audio_bytes_queue.get(timeout=1)

                if self.is_stopped():
                    continue

                # logging.debug(f'Playing {len(audio_data)} bytes of audio data')
                self._speaking = True
                player.play_data(audio_data)
                self._speaking = False

            except queue.Empty:
                continue
            except Exception as e:
                self._speaking = False
                logging.error(f'Error while playing audio: {e}')

    def speak(
        self,
        text: str,
        voice: Optional[Voice] = None,
        response_format: str = None,  # ignored
        **kwargs,
    ):
        return self.transcribe_to_stream(
            text=text,
            stream=self._audio_bytes_queue,
            voice=voice,
            response_format=response_format,
            **kwargs,
        )

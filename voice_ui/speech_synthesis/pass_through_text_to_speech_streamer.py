import logging
import queue
import threading
from typing import Dict, List, Union

from ..audio_io.audio_data import AudioData
from ..audio_io.player import Player
from .text_to_speech_streamer import TextToSpeechAudioStreamer


class ByteQueue:
    def __init__(self):
        self._lock = threading.Lock()
        self._sem = threading.Semaphore()
        self._data = b''

    def put(self, data):
        with self._lock:
            self._data += data
            self._sem.release()

    def get(self, timeout=None) -> bytes:
        acquired = self._sem.acquire(blocking=True, timeout=timeout)
        if not acquired:
            raise TimeoutError()

        with self._lock:
            audio_data = self._data
            self._data = b''

        return audio_data


class PassThroughTextToSpeechAudioStreamer(TextToSpeechAudioStreamer):
    def __init__(self):
        self._stopped = False
        self._speaking = False
        self._lock = threading.Lock()

        self._terminated = False
        self._speaker_thread = threading.Thread(
            target=self._speaker_thread_function,
            daemon=True
        )

        self._data_queue = queue.Queue()
        self._player = Player()

        self._speaker_thread.start()

    def terminate(self):
        self.stop()
        self._terminated = True
        if self._speaker_thread.is_alive():
            self._speaker_thread.join(timeout=5)

    @staticmethod
    def name():
        return "passthrough"

    def __del__(self):
        self.terminate()

    def _speaker_thread_function(self):
        self._terminated = False

        while not self._terminated:
            try:
                audio_data = self._data_queue.get(timeout=1)

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
        return None

    def speak(
        self,
        text: Union[AudioData, bytes],
        **kwargs,
    ):
        if isinstance(text, str):
            raise AttributeError("This stream does not support text")

        # Reset the stopped flag
        with self._lock:
            self._stopped = False

        if isinstance(text, AudioData):
            audio_data = text.content
        else:
            audio_data = text

        logging.debug(f'Speaking {len(audio_data)} bytes of audio')

        self._data_queue.put(audio_data)

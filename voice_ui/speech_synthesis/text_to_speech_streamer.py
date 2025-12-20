from abc import ABC, abstractmethod
from typing import Dict, List


class TextToSpeechAudioStreamer(ABC):  # pragma: no cover
    @staticmethod
    @abstractmethod
    def name(self):
        pass

    @abstractmethod
    def terminate(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def is_stopped(self) -> bool:
        pass

    @abstractmethod
    def is_speaking(self):
        pass

    @abstractmethod
    def available_voices(self) -> List[Dict]:
        pass

    @abstractmethod
    def speech_queue_size(self) -> int:
        pass

    @abstractmethod
    def speak(
        self,
        text: str,
        **kwargs,
    ):
        pass

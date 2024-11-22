from abc import ABC, abstractmethod, abstractstaticmethod
from typing import Dict, List


class TextToSpeechAudioStreamer(ABC):
    @abstractstaticmethod
    def name(self):
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
    def speak(
        self,
        text: str,
        **kwargs,
    ):
        pass

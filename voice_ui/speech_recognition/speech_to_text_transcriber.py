from abc import ABC, abstractmethod

from ..audio_io.audio_data import AudioData


class SpeechToTextTranscriber(ABC):  # pragma: no cover

    @staticmethod
    @abstractmethod
    def name() -> str:
        pass

    @abstractmethod
    def transcribe(self, audio_data: AudioData) -> str:
        pass

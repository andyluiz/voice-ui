from abc import ABC, abstractmethod, abstractstaticmethod

from ..audio_io.audio_data import AudioData


class SpeechToTextTranscriber(ABC):

    @abstractstaticmethod
    def name() -> str:
        pass

    @abstractmethod
    def transcribe(self, audio_data: AudioData) -> str:
        pass

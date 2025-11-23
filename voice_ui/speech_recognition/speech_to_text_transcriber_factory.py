import logging
import threading
from typing import Type

from .speech_to_text_transcriber import SpeechToTextTranscriber

logger = logging.getLogger(__name__)


class TranscriberFactory:
    _transcribers = {}
    _lock = threading.Lock()

    @classmethod
    def create(cls, transcription_engine_name) -> SpeechToTextTranscriber:
        logger.info(f"Creating transcriber for '{transcription_engine_name}'")

        if transcription_engine_name is None:
            return None

        with cls._lock:
            if transcription_engine_name in cls._transcribers:
                return cls._transcribers[transcription_engine_name]()

        raise RuntimeError(f"Engine '{transcription_engine_name}' is not available")

    @classmethod
    def register_transcriber(cls, name: str, transcriber_class: Type[SpeechToTextTranscriber]):
        with cls._lock:
            cls._transcribers[name] = transcriber_class

    @classmethod
    def unregister_transcriber(cls, name: str):
        with cls._lock:
            if name in cls._transcribers:
                del cls._transcribers[name]
            else:
                raise KeyError(f"Transcriber not found: {name}")


# Register available transcribers (best-effort imports)
try:
    from .openai_local_whisper import LocalWhisperTranscriber

    TranscriberFactory.register_transcriber(LocalWhisperTranscriber.name(), LocalWhisperTranscriber)
except ModuleNotFoundError:
    pass

try:
    from .openai_whisper import WhisperTranscriber

    TranscriberFactory.register_transcriber(WhisperTranscriber.name(), WhisperTranscriber)
except ModuleNotFoundError:
    pass

import logging
import threading
from typing import Type

from .pass_through_text_to_speech_streamer import PassThroughTextToSpeechAudioStreamer
from .text_to_speech_streamer import TextToSpeechAudioStreamer

logger = logging.getLogger(__name__)


class TTSFactory:
    _tts_engines = {}
    _lock = threading.Lock()

    @classmethod
    def create(cls, tts_engine_name) -> TextToSpeechAudioStreamer:
        logger.info(f"Creating TTS streamer for '{tts_engine_name}'")

        with cls._lock:
            if tts_engine_name in cls._tts_engines:
                return cls._tts_engines[tts_engine_name]()

        raise RuntimeError(f"Engine '{tts_engine_name}' is not available")

    @classmethod
    def register_tts(cls, name: str, tts_class: Type[TextToSpeechAudioStreamer]):
        with cls._lock:
            cls._tts_engines[name] = tts_class

    @classmethod
    def unregister_tts(cls, name: str):
        with cls._lock:
            if name in cls._tts_engines:
                del cls._tts_engines[name]
            else:
                raise KeyError(f"TTS engine not found: {name}")


# Register built-in engines
TTSFactory.register_tts(PassThroughTextToSpeechAudioStreamer.name(), PassThroughTextToSpeechAudioStreamer)

try:
    from .google_text_to_speech_streamer import GoogleTextToSpeechAudioStreamer

    TTSFactory.register_tts(GoogleTextToSpeechAudioStreamer.name(), GoogleTextToSpeechAudioStreamer)
except ModuleNotFoundError:
    pass

try:
    from .openai_text_to_speech_streamer import OpenAITextToSpeechAudioStreamer

    TTSFactory.register_tts(OpenAITextToSpeechAudioStreamer.name(), OpenAITextToSpeechAudioStreamer)
except ModuleNotFoundError:
    pass

import threading
from typing import Type

from .vad_i import IVoiceActivityDetector


class VADFactory:
    vad_classes = {}
    _lock = threading.Lock()

    @classmethod
    def create(cls, vad_type: str, **kwargs) -> IVoiceActivityDetector:
        with cls._lock:
            if vad_type in cls.vad_classes:
                return cls.vad_classes[vad_type](**kwargs)
            else:
                raise ValueError(f"Invalid VAD type: {vad_type}")

    @classmethod
    def register_vad(cls, vad_type: str, vad_class: Type[IVoiceActivityDetector]):
        with cls._lock:
            cls.vad_classes[vad_type] = vad_class

    @classmethod
    def unregister_vad(cls, vad_type: str):
        with cls._lock:
            if vad_type in cls.vad_classes:
                del cls.vad_classes[vad_type]
            else:
                raise KeyError(f"VAD type not found: {vad_type}")


try:
    from .vad_picovoice import PicoVoiceVAD

    # Register the VAD with the factory
    VADFactory.register_vad(PicoVoiceVAD.__name__, PicoVoiceVAD)
except ImportError:
    pass

try:
    from .vad_funasr import FunASRVAD

    # Register the VAD with the factory
    VADFactory.register_vad(FunASRVAD.__name__, FunASRVAD)
except ImportError:
    pass

try:
    from .vad_silero import SileroVAD

    # Register the VAD with the factory
    VADFactory.register_vad(SileroVAD.__name__, SileroVAD)
except ImportError:
    pass

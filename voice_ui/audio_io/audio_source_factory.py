import logging
import threading
from typing import Optional, Type

from .microphone import MicrophoneStream
from .virtual_microphone import VirtualMicrophone

logger = logging.getLogger(__name__)


class AudioSourceFactory:
    _sources = {}
    _lock = threading.Lock()

    @classmethod
    def create(cls, source_name: Optional[str], **kwargs):
        logger.info(f"Creating audio source for '{source_name}'")

        if source_name is None:
            return None

        with cls._lock:
            if source_name in cls._sources:
                return cls._sources[source_name](**kwargs)

        raise RuntimeError(f"Engine '{source_name}' is not available")

    @classmethod
    def register_source(cls, name: str, source_class: Type):
        with cls._lock:
            cls._sources[name] = source_class

    @classmethod
    def unregister_source(cls, name: str):
        with cls._lock:
            if name in cls._sources:
                del cls._sources[name]
            else:
                raise KeyError(f"Audio source not found: {name}")

    @classmethod
    def list_sources(cls):
        with cls._lock:
            return list(cls._sources.keys())


# Register built-in sources
AudioSourceFactory.register_source("microphone", MicrophoneStream)
AudioSourceFactory.register_source("remote", VirtualMicrophone)

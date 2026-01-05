import logging
import threading
from typing import Optional, Type

from .player import Player
from .virtual_player import VirtualPlayer

logger = logging.getLogger(__name__)


class AudioSinkFactory:
    _sinks = {}
    _lock = threading.Lock()

    @classmethod
    def create(cls, sink_name: Optional[str], **kwargs):
        logger.info(f"Creating audio sink for '{sink_name}'")

        if sink_name is None:
            return None

        with cls._lock:
            if sink_name in cls._sinks:
                return cls._sinks[sink_name](**kwargs)

        raise RuntimeError(f"Engine '{sink_name}' is not available")

    @classmethod
    def register_sink(cls, name: str, sink_class: Type):
        with cls._lock:
            cls._sinks[name] = sink_class

    @classmethod
    def unregister_sink(cls, name: str):
        with cls._lock:
            if name in cls._sinks:
                del cls._sinks[name]
            else:
                raise KeyError(f"Audio sink not found: {name}")

    @classmethod
    def list_sinks(cls):
        with cls._lock:
            return list(cls._sinks.keys())


# Register built-in sinks
AudioSinkFactory.register_sink("speaker", Player)
AudioSinkFactory.register_sink("remote", VirtualPlayer)

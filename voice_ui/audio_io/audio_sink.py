from abc import ABC, abstractmethod


class AudioSink(ABC):
    """Abstract interface for audio sinks (local and remote).

    Implementations must provide:

    - `rate`: sample rate in Hz
    - `chunk_size`: number of samples per chunk yielded
    - `channels`: number of audio channels
    - `sample_size`: bytes per sample (e.g., 2 for 16-bit PCM)
    """

    @property
    @abstractmethod
    def channels(self) -> int: ...

    @property
    @abstractmethod
    def rate(self) -> int: ...

    @property
    @abstractmethod
    def chunk_size(self) -> int: ...

    @property
    @abstractmethod
    def sample_size(self) -> int: ...

    @abstractmethod
    def play(self, audio_data: bytes) -> None: ...

    @abstractmethod
    def is_playing(self) -> bool: ...

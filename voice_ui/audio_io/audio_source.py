from abc import ABC, abstractmethod
from typing import Iterator


class AudioSource(ABC):
    """Abstract interface for audio sources (local and remote).

    Implementations must provide:

    - `rate`: sample rate in Hz
    - `chunk_size`: number of samples per chunk yielded
    - `channels`: number of audio channels
    - `sample_format`: backend-specific sample format constant (if any)
    - `sample_size`: bytes per sample (e.g., 2 for 16-bit PCM)
    - `resume()`: start or resume streaming from the underlying source
    - `pause()`: pause or stop streaming (generators should eventually end)
    - `generator()`: yield PCM byte chunks from the source
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
    def sample_format(self): ...

    @property
    @abstractmethod
    def sample_size(self) -> int: ...

    @abstractmethod
    def resume(self) -> None: ...

    @abstractmethod
    def pause(self) -> None: ...

    @abstractmethod
    def generator(self) -> Iterator[bytes]: ...

    # No concrete __init__ or backing attributes here; each implementation
    # is responsible for maintaining its own internal state.

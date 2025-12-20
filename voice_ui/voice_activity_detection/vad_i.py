from abc import ABC, abstractmethod, abstractproperty
from typing import List, Union


class IVoiceActivityDetector(ABC):  # pragma: no cover
    @abstractmethod
    def process(self, data: Union[bytes, List], **kwargs) -> bool:
        pass

    @abstractproperty
    def frame_length(self) -> int:
        pass

    @abstractproperty
    def sample_rate(self) -> int:
        pass

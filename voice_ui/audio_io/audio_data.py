class AudioData:
    def __init__(self, content: bytes, sample_size: int, rate: int, channels: int):
        self.content = content
        self.sample_size = sample_size
        self.rate = rate
        self.channels = channels

    def __eq__(self, other):
        if not isinstance(other, AudioData):
            return False

        return (
            self.content == other.content
            and self.sample_size == other.sample_size
            and self.rate == other.rate
            and self.channels == other.channels
        )

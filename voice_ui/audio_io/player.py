import wave
from typing import Optional, Tuple

import pyaudio

from .audio_sink import AudioSink
from .pyaudio_load_message_suppressor import no_alsa_and_jack_errors


class Player(AudioSink):
    def __init__(
        self,
        format: int = pyaudio.paInt16,
        channels: int = 1,
        rate: int = 24_000,
        chunk_size: int = 4096,
        device_name: Optional[str] = None,
        device_index: Optional[int] = None,
    ):
        if device_name is not None:
            device_index = self.find_device_index(device_name)

        self._channels = channels
        self._rate = rate
        self._chunk_size = chunk_size
        self._format = format
        self._sample_size = pyaudio.get_sample_size(format)
        self._is_playing = False

        # Open an audio stream
        with no_alsa_and_jack_errors():
            self._audio_interface = pyaudio.PyAudio()

        self._audio_stream = self._audio_interface.open(
            format=format,
            channels=channels,
            rate=rate,
            frames_per_buffer=chunk_size,
            output=True,
            output_device_index=device_index,
        )

    def __del__(self):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self._audio_interface.terminate()

    @property
    def channels(self) -> int:
        return self._channels

    @property
    def rate(self) -> int:
        return self._rate

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    @property
    def sample_size(self) -> int:
        return self._sample_size

    def is_playing(self) -> bool:
        return self._is_playing

    def play(self, audio_data: bytes) -> None:
        """Play audio data"""
        if len(audio_data) == 0:
            return

        self._is_playing = True
        self._audio_stream.write(audio_data)

    def get_devices(self, capture_devices: bool = False) -> Tuple[str, ...]:
        device_count = self._audio_interface.get_device_count()
        devices = []

        for i in range(device_count):
            info = self._audio_interface.get_device_info_by_index(i)
            if (capture_devices and info["maxInputChannels"] > 0) or (
                not capture_devices and info["maxOutputChannels"] > 0
            ):
                devices.append(info["name"])

        return tuple(devices)

    def find_device_index(self, device_name: str) -> int:
        for i in range(self._audio_interface.get_device_count()):
            info = self._audio_interface.get_device_info_by_index(i)
            if info["name"] == device_name:
                return i
        raise RuntimeError(f"Device `{device_name}` not found")

    def play_file(
        self,
        file_path: str,
        device_name: Optional[str] = None,
        device_index: Optional[int] = None,
    ):
        if device_name is not None:
            device_index = self.find_device_index(device_name)

        chunk = 2048

        with wave.open(file_path, "rb") as wf:
            stream = self._audio_interface.open(
                format=self._audio_interface.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
                output_device_index=device_index,
            )

            while len(data := wf.readframes(chunk)):
                stream.write(data)

        stream.stop_stream()
        stream.close()

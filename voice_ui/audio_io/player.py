import wave
from typing import Optional, Tuple

import pyaudio

from .pyaudio_load_message_suppressor import no_alsa_and_jack_errors


class Player:
    def __init__(
        self,
        format: int = pyaudio.paInt16,
        channels: int = 1,
        rate: int = 24_000,
        device_name: Optional[str] = None,
        device_index: Optional[int] = None,
    ):
        if device_name is not None:
            device_index = self.find_device_index(device_name)

        # Open an audio stream
        with no_alsa_and_jack_errors():
            self._audio_interface = pyaudio.PyAudio()

        self._stream = self._audio_interface.open(
            format=format,
            channels=channels,
            rate=rate,
            frames_per_buffer=4096,
            output=True,
            output_device_index=device_index,
        )

    def __del__(self):
        self._stream.stop_stream()
        self._stream.close()
        self._audio_interface.terminate()

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

    def play_data(
        self,
        audio_data: bytes,
    ):
        if len(audio_data) == 0:
            return

        self._stream.write(audio_data)

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

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

        # Lazily created audio interface and stream to support CI/headless envs
        self._audio_interface = None
        self._audio_stream = None
        self._output_device_index = device_index

    def __del__(self):
        try:
            if getattr(self, "_audio_stream", None) is not None:
                try:
                    self._audio_stream.stop_stream()
                except Exception:
                    pass
                try:
                    self._audio_stream.close()
                except Exception:
                    pass
            if getattr(self, "_audio_interface", None) is not None:
                try:
                    self._audio_interface.terminate()
                except Exception:
                    pass
        except Exception:
            # Be defensive in destructors; do not raise from __del__
            pass

    def _init_audio_interface(self):
        """Initialize the PyAudio interface if not already present."""
        if self._audio_interface is None:
            with no_alsa_and_jack_errors():
                self._audio_interface = pyaudio.PyAudio()

    def _ensure_audio_stream(self):
        """Open the output audio stream if not already opened."""
        if self._audio_stream is None:
            self._init_audio_interface()
            try:
                self._audio_stream = self._audio_interface.open(
                    format=self._format,
                    channels=self._channels,
                    rate=self._rate,
                    frames_per_buffer=self._chunk_size,
                    output=True,
                    output_device_index=self._output_device_index,
                )
            except OSError:
                # Running in headless/CI environment without audio device; leave
                # _audio_stream as None and let callers handle the missing stream.
                self._audio_stream = None

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
        self._ensure_audio_stream()
        if self._audio_stream is not None:
            self._audio_stream.write(audio_data)
        else:
            # No audio device available; act as a no-op
            self._is_playing = False

    def get_devices(self, capture_devices: bool = False) -> Tuple[str, ...]:
        self._init_audio_interface()
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
        self._init_audio_interface()
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
            # Open a temporary stream for file playback
            self._init_audio_interface()
            try:
                stream = self._audio_interface.open(
                    format=self._audio_interface.get_format_from_width(
                        wf.getsampwidth()
                    ),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True,
                    output_device_index=device_index,
                )
            except OSError:
                # No audio device available; treat as no-op
                return

            while len(data := wf.readframes(chunk)):
                stream.write(data)

            stream.stop_stream()
            stream.close()

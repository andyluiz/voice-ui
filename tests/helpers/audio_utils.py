import math
import struct
import types
import wave
from pathlib import Path
from typing import Optional


def generate_sine_wav(path: Path, duration: float = 0.5, freq: float = 440, rate: int = 16000):
    """Generate a mono 16-bit WAV sine wave to `path`.

    This helper is intentionally tiny and avoids external deps.
    """
    nframes = int(duration * rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        for i in range(nframes):
            val = int(32767.0 * 0.5 * math.sin(2.0 * math.pi * freq * i / rate))
            wf.writeframes(struct.pack("<h", val))


class FakeMicrophoneVADStream:
    """Fake replacement for MicrophoneVADStream used by tests.

    Provides minimal attributes/methods used by the `SpeechDetector`.
    """

    class DetectionMode:
        HOTWORD = 1
        VOICE_ACTIVITY = 2

    def __init__(self, wav_path: Optional[Path] = None, rate: int = 16000, chunk: int = 800, **_):
        self._wav_path = Path(wav_path) if wav_path is not None else None
        self._rate = rate
        self._chunk = chunk
        self._closed = True

    @property
    def channels(self):
        return 1

    @property
    def sample_size(self):
        return 2

    @property
    def rate(self):
        return self._rate

    @property
    def detection_mode(self):
        return self.DetectionMode.VOICE_ACTIVITY

    def set_detection_mode(self, mode):
        self._detection_mode = mode

    def convert_duration_to_chunks(self, duration: float) -> int:
        return int(math.ceil(duration * self._rate / self._chunk))

    @staticmethod
    def convert_data(byte_data):
        int16_values = struct.unpack(f"{len(byte_data) // 2}h", byte_data)
        return list(int16_values)

    def resume(self):
        self._closed = False

    def pause(self):
        self._closed = True

    def generator(self):
        if self._wav_path is None or not self._wav_path.exists():
            return

        with wave.open(str(self._wav_path), "rb") as wf:
            frames = wf.readframes(1024)
            while frames and not self._closed:
                bytes_per_frame = wf.getsampwidth() * wf.getnchannels()
                chunk_bytes = self._chunk * bytes_per_frame
                for i in range(0, len(frames), chunk_bytes):
                    yield frames[i:i + chunk_bytes]
                frames = wf.readframes(1024)

        # signal end of speech
        yield b""


def inject_minimal_audio_and_hotword_mocks():
    """Insert minimal `pyaudio` and `pvporcupine` modules into sys.modules.

    Tests import code that may import these native modules; in CI we provide
    lightweight, pure-Python stand-ins so tests can run without native deps.
    """
    import sys

    # Minimal fake pyaudio
    fake_pyaudio = types.ModuleType("pyaudio")
    fake_pyaudio.paInt16 = 8

    class _FakeStream:
        def start_stream(self):
            pass

        def stop_stream(self):
            pass

        def close(self):
            pass

    class _FakePyAudio:
        def __init__(self, *a, **kw):
            pass

        def get_sample_size(self, fmt):
            return 2

        def open(self, *a, **kw):
            return _FakeStream()

        def terminate(self):
            pass

    fake_pyaudio.PyAudio = _FakePyAudio

    # Minimal fake pvporcupine
    fake_pv = types.ModuleType("pvporcupine")
    fake_pv.KEYWORD_PATHS = {"demo": "demo.ppn"}

    class _FakePorcupineHandle:
        frame_length = 512

        def process(self, frame):
            return -1

        def delete(self):
            pass

    def _fake_create(*_a, **_kw):
        return _FakePorcupineHandle()

    fake_pv.create = _fake_create

    sys.modules.setdefault("pyaudio", fake_pyaudio)
    sys.modules.setdefault("pvporcupine", fake_pv)

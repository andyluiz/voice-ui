import os
import tempfile
import unittest
import wave

from voice_ui.audio_io.player import Player


class FakeStream:
    def __init__(self):
        self.written = b""
        self.stopped = False
        self.closed = False

    def write(self, data):
        self.written += data

    def stop_stream(self):
        self.stopped = True

    def close(self):
        self.closed = True


class FakeAudioInterface:
    def __init__(self, devices=None):
        self._devices = devices or []
        self.open_called = False

    def terminate(self):
        # no-op for tests
        return None

    def get_device_count(self):
        return len(self._devices)

    def get_device_info_by_index(self, i):
        return self._devices[i]

    def get_format_from_width(self, w):
        return 123

    def open(self, **kwargs):
        self.open_called = True
        return FakeStream()


def make_player_with_fake():
    # Create a Player-like object without invoking actual pyaudio
    p = object.__new__(Player)
    p._audio_interface = FakeAudioInterface(
        devices=[
            {"name": "out", "maxOutputChannels": 1, "maxInputChannels": 0},
            {"name": "in", "maxInputChannels": 1, "maxOutputChannels": 0},
        ]
    )
    p._audio_stream = FakeStream()
    return p


class TestPlayer(unittest.TestCase):
    def test_get_devices(self):
        p = make_player_with_fake()
        out = p.get_devices(capture_devices=False)
        self.assertIn("out", out)

        caps = p.get_devices(capture_devices=True)
        self.assertIn("in", caps)

    def test_find_device_index_success_and_failure(self):
        p = make_player_with_fake()
        idx = p.find_device_index("out")
        self.assertEqual(idx, 0)

        with self.assertRaises(RuntimeError):
            p.find_device_index("non-existent")

    def test_play_data_empty_and_non_empty(self):
        p = make_player_with_fake()
        p._audio_stream = FakeStream()
        p.play(b"")
        self.assertEqual(p._audio_stream.written, b"")

        p._audio_stream = FakeStream()
        p.play(b"abc")
        self.assertEqual(p._audio_stream.written, b"abc")

    def test_play_file_reads_wav_and_writes(self):
        # create temporary wav file
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(8000)
            wf.writeframes(b"\x00\x00" * 100)

        class AI(FakeAudioInterface):
            def open(self, **kwargs):
                return FakeStream()

        p = object.__new__(Player)
        p._audio_interface = AI()
        # ensure _stream exists so __del__ won't fail during GC
        p._audio_stream = FakeStream()

        # should not raise
        p.play_file(path)

        os.unlink(path)


if __name__ == "__main__":
    unittest.main()

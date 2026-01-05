import unittest

from voice_ui.audio_io.audio_source import AudioSource
from voice_ui.audio_io.audio_source_factory import AudioSourceFactory
from voice_ui.audio_io.virtual_microphone import VirtualMicrophone
from voice_ui.speech_detection.vad_audio_source import VADAudioSource


class TestRemoteMicrophone(unittest.TestCase):
    def test_push_read_generator_and_stop(self):
        rm = VirtualMicrophone()

        # push some frames before creating the generator
        rm.push_frame(b"a")
        rm.push_frame(b"b")

        gen = rm.generator()
        first = next(gen)
        # VirtualMicrophone yields frames as they come
        self.assertEqual(first, b"a")
        second = next(gen)
        self.assertEqual(second, b"b")

        # stop should signal generator to terminate
        rm.stop()
        with self.assertRaises(StopIteration):
            next(gen)

    def test_read_returns_pushed_frame(self):
        rm = VirtualMicrophone()
        rm.push_frame(b"zzz")
        val = rm.read(timeout=0.1)
        self.assertEqual(val, b"zzz")


class SimpleSource(AudioSource):
    def __init__(self):
        self._rate = 16000
        self._chunk = 800
        self._channels = 1
        self._sample_format = None
        self._sample_size = 2

    @property
    def channels(self) -> int:
        return self._channels

    @property
    def rate(self) -> int:
        return self._rate

    @property
    def chunk_size(self) -> int:
        return self._chunk

    @property
    def sample_format(self):
        return self._sample_format

    @property
    def sample_size(self) -> int:
        return self._sample_size

    def resume(self):
        pass

    def pause(self):
        pass

    def generator(self):
        # yield a single chunk then terminate
        yield b"\x00\x01"


class TestMicrophoneVADInjection(unittest.TestCase):
    def test_injected_source_used(self):
        # Ensure hotword detector does not attempt to load real keyword files
        from unittest.mock import patch

        class DummyHandle:
            def delete(self):
                pass

        with patch(
            "voice_ui.speech_detection.hotword_detector.pvporcupine.create",
            return_value=DummyHandle(),
        ):
            src = SimpleSource()
            m = VADAudioSource(source_instance=src)
        # when external source is provided, rate and chunk_size should match
        self.assertEqual(m.rate, src.rate)
        self.assertEqual(m.chunk_size, src.chunk_size)

    def test_factory_path_creates_source(self):
        # register a temporary factory class
        AudioSourceFactory.register_source("simple_test_src", SimpleSource)
        from unittest.mock import patch

        class DummyHandle:
            def delete(self):
                pass

        try:
            with patch(
                "voice_ui.speech_detection.hotword_detector.pvporcupine.create",
                return_value=DummyHandle(),
            ):
                m = VADAudioSource(source_name="simple_test_src")
                self.assertIsNotNone(m._source)
                self.assertEqual(m.rate, 16000)
        finally:
            try:
                AudioSourceFactory.unregister_source("simple_test_src")
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()

import unittest

from voice_ui.audio_io.audio_source import AudioSource
from voice_ui.audio_io.audio_source_factory import AudioSourceFactory


class DummySource(AudioSource):
    def __init__(self, rate=8000, chunk=400, channels=1, sample_size=None):
        self._rate = rate
        self._chunk = chunk
        self._channels = channels
        self._sample_size = sample_size or 2
        self._sample_format = None
        self._running = False

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
        self._running = True

    def pause(self):
        self._running = False

    def generator(self):
        # simple generator for testing
        yield b"x"


class TestAudioSourceBase(unittest.TestCase):
    def test_defaults_and_sample_size(self):
        d = DummySource()
        # defaults come from DummySource ctor
        self.assertEqual(d.rate, 8000)
        self.assertEqual(d.chunk_size, 400)
        self.assertEqual(d.channels, 1)

        # explicit sample_size overrides
        d2 = DummySource(sample_size=4)
        self.assertEqual(d2.sample_size, 4)


class TestAudioSourceFactory(unittest.TestCase):
    def test_create_list_register_unregister(self):
        # create with None returns None
        self.assertIsNone(AudioSourceFactory.create(None))

        # register a temporary source and create it

        AudioSourceFactory.register_source("dummy_test", DummySource)
        try:
            inst = AudioSourceFactory.create("dummy_test", rate=1234)
            self.assertIsInstance(inst, DummySource)
            self.assertEqual(inst.rate, 1234)

            names = AudioSourceFactory.list_sources()
            self.assertIn("dummy_test", names)

            # unregister
            AudioSourceFactory.unregister_source("dummy_test")
            self.assertNotIn("dummy_test", AudioSourceFactory.list_sources())

        finally:
            # ensure cleanup if something failed
            try:
                AudioSourceFactory.unregister_source("dummy_test")
            except Exception:
                pass

    def test_unregister_nonexistent_raises(self):
        with self.assertRaises(KeyError):
            AudioSourceFactory.unregister_source("no_such_source_12345")


if __name__ == "__main__":
    unittest.main()

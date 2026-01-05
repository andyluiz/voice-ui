import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from voice_ui.audio_io.audio_source_base import AudioSourceBase
from voice_ui.speech_detection.vad_audio_source import VADAudioSource


class FakeSource(AudioSourceBase):
    """Simple AudioSourceBase implementation for testing.

    It yields chunks from a predefined list and then stops.
    """

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self._rate = 16000
        self._chunk = 160
        self._channels = 1
        self._sample_format = None
        self._sample_size = 2
        self._resumed = False

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

    def resume(self) -> None:
        self._resumed = True

    def pause(self) -> None:
        self._resumed = False

    def generator(self):
        for c in self._chunks:
            yield c


class TestVADAudioSource(unittest.TestCase):

    @patch("voice_ui.speech_detection.vad_audio_source.HotwordDetector")
    @patch("voice_ui.voice_activity_detection.vad_factory.VADFactory.create")
    def setUp(self, mock_vad_factory_create, mock_hotword_detector_cls):
        self.mock_hotword_detector = MagicMock()
        mock_hotword_detector_cls.return_value = self.mock_hotword_detector

        self.mock_vad = MagicMock(frame_length=512)
        mock_vad_factory_create.return_value = self.mock_vad

    @patch("voice_ui.speech_detection.vad_audio_source.HotwordDetector", MagicMock())
    @patch("voice_ui.voice_activity_detection.vad_factory.VADFactory.create")
    def test_init_with_audio_length_out_of_limits_negative(
        self, mock_vad_factory_create
    ):
        self.mock_vad = MagicMock(frame_length=512)
        mock_vad_factory_create.return_value = self.mock_vad

        source = FakeSource([b"a"])
        stream = VADAudioSource(pre_speech_duration=-1, source_instance=source)

        self.assertEqual(stream._vad, self.mock_vad)
        self.assertEqual(stream._pre_speech_queue.maxlen, 1)
        mock_vad_factory_create.assert_called_once()

    @patch("voice_ui.speech_detection.vad_audio_source.HotwordDetector", MagicMock())
    @patch("voice_ui.voice_activity_detection.vad_factory.VADFactory.create")
    def test_init_with_audio_length_out_of_limits_high(self, mock_vad_factory_create):
        self.mock_vad = MagicMock(frame_length=512)
        mock_vad_factory_create.return_value = self.mock_vad

        source = FakeSource([b"a"])
        stream = VADAudioSource(pre_speech_duration=10, source_instance=source)

        self.assertEqual(stream._vad, self.mock_vad)
        self.assertEqual(stream._pre_speech_queue.maxlen, 150)
        mock_vad_factory_create.assert_called_once()

    def test_convert_data(self):
        byte_data = b"\x01\x02\x03\x04"
        result = VADAudioSource.convert_data(byte_data)
        self.assertEqual(result, [513, 1027])

    def test_timer_expired_with_no_timeout(self):
        start_time = datetime.now()
        result = VADAudioSource._timer_expired(start_time)
        self.assertEqual(result, False)

    def test_timer_expired_with_timeout_expired(self):
        start_time = datetime.now() - timedelta(seconds=1)
        result = VADAudioSource._timer_expired(start_time, timeout=1)
        self.assertEqual(result, True)

    def test_timer_expired_with_timeout_not_expired(self):
        start_time = datetime.now() - timedelta(seconds=1)
        result = VADAudioSource._timer_expired(start_time, timeout=10)
        self.assertEqual(result, False)

    @patch("voice_ui.speech_detection.vad_audio_source.HotwordDetector", MagicMock())
    @patch("voice_ui.voice_activity_detection.vad_factory.VADFactory.create")
    def test_detect_speech_simple(self, mock_vad_factory_create):
        # Simulate three chunks where middle one is speech; pre-speech
        # buffering will return the first chunk along with the speech chunk.
        self.mock_vad = MagicMock(frame_length=1)
        mock_vad_factory_create.return_value = self.mock_vad

        # Each chunk must be >= frame_length * sample_size (1 * 2 = 2 bytes)
        chunks = [b"ab", b"cd", b"ef"]
        source = FakeSource(chunks)
        stream = VADAudioSource(pre_speech_duration=0.0, source_instance=source)

        # below, above, below
        self.mock_vad.process.side_effect = [False, True, False]

        result = list(stream.generator())

        # Expect: start-of-speech yields pre-speech + speech (b"ab", b"cd"),
        # then an end-of-utterance marker b"".
        self.assertEqual(result, [b"ab", b"cd", b""])


if __name__ == "__main__":
    unittest.main()

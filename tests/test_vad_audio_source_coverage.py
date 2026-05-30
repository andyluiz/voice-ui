"""Targeted coverage tests for VADAudioSource edge cases."""

import unittest
from unittest.mock import MagicMock, patch

from voice_ui.audio_io.audio_source import AudioSource
from voice_ui.speech_detection.vad_audio_source import VADAudioSource


# ---------------------------------------------------------------------------
# Minimal FakeSource used throughout
# ---------------------------------------------------------------------------


class FakeSource(AudioSource):
    def __init__(
        self,
        chunks=None,
        raise_on_generator=False,
        raise_on_resume=False,
        raise_on_pause=False,
    ):
        self._chunks = list(chunks or [])
        self._raise_on_generator = raise_on_generator
        self._raise_on_resume = raise_on_resume
        self._raise_on_pause = raise_on_pause
        self._rate = 16000
        self._chunk = 160
        self._channels = 1
        self._sample_format = None
        self._sample_size = 2

    @property
    def channels(self):
        return self._channels

    @property
    def rate(self):
        return self._rate

    @property
    def chunk_size(self):
        return self._chunk

    @property
    def sample_format(self):
        return self._sample_format

    @property
    def sample_size(self):
        return self._sample_size

    def resume(self):
        if self._raise_on_resume:
            raise RuntimeError("resume error")

    def pause(self):
        if self._raise_on_pause:
            raise RuntimeError("pause error")

    def generator(self):
        if self._raise_on_generator:
            raise RuntimeError("generator error")
        yield from self._chunks


def _make_stream(source, **kwargs):
    """Create a VADAudioSource with mocked VAD and hotword detector."""
    mock_vad = MagicMock(frame_length=None)
    mock_vad.process.return_value = False

    with patch(
        "voice_ui.speech_detection.vad_audio_source.VADFactory.create",
        return_value=mock_vad,
    ), patch("voice_ui.speech_detection.vad_audio_source.HotwordDetector"):
        stream = VADAudioSource(source_instance=source, **kwargs)

    stream._vad = mock_vad
    return stream


# ---------------------------------------------------------------------------
# Init: False branches of None-defaults
# ---------------------------------------------------------------------------


class TestVADAudioSourceInitDefaults(unittest.TestCase):
    """All None-default if-branches have a False path when values are provided."""

    def test_explicit_all_params_skips_defaults(self):
        source = FakeSource()
        with patch(
            "voice_ui.speech_detection.vad_audio_source.VADFactory.create",
            return_value=MagicMock(frame_length=None),
        ), patch("voice_ui.speech_detection.vad_audio_source.HotwordDetector"):
            stream = VADAudioSource(
                threshold=0.6,
                pre_speech_duration=0.3,
                post_speech_duration=0.4,
                vad_engine="SileroVAD",
                additional_keyword_paths={"kw": "/path/to/kw"},
                source_instance=source,
            )

        self.assertEqual(stream._threshold, 0.6)
        self.assertEqual(stream._pre_speech_duration, 0.3)
        self.assertEqual(stream._post_speech_duration, 0.4)


# ---------------------------------------------------------------------------
# Properties and simple methods
# ---------------------------------------------------------------------------


class TestVADAudioSourceProperties(unittest.TestCase):

    def setUp(self):
        self.source = FakeSource()
        self.stream = _make_stream(self.source)

    def test_channels_property(self):
        self.assertEqual(self.stream.channels, 1)

    def test_sample_format_property(self):
        self.assertIsNone(self.stream.sample_format)

    def test_detection_mode_property(self):
        mode = self.stream.detection_mode
        self.assertEqual(mode, VADAudioSource.DetectionMode.VOICE_ACTIVITY)

    def test_set_detection_mode(self):
        self.stream.set_detection_mode(VADAudioSource.DetectionMode.HOTWORD)
        self.assertEqual(
            self.stream._detection_mode, VADAudioSource.DetectionMode.HOTWORD
        )

    def test_available_keywords(self):
        self.stream._hotword_detector = MagicMock()
        self.stream._hotword_detector.available_keywords.return_value = ["hey"]
        self.assertEqual(self.stream.available_keywords, ["hey"])

    def test_pause_clears_prespeech_queue(self):
        self.stream._pre_speech_queue.append(b"a")
        self.stream._pre_speech_queue.append(b"b")
        self.stream.pause()
        self.assertEqual(len(self.stream._pre_speech_queue), 0)
        self.assertTrue(self.stream._closed)

    def test_resume_exception_is_swallowed(self):
        source = FakeSource(raise_on_resume=True)
        stream = _make_stream(source)
        # Should not raise
        stream.resume()

    def test_pause_exception_is_swallowed(self):
        source = FakeSource(raise_on_pause=True)
        stream = _make_stream(source)
        # Should not raise
        stream.pause()


# ---------------------------------------------------------------------------
# convert_data edge cases
# ---------------------------------------------------------------------------


class TestConvertData(unittest.TestCase):

    def test_empty_bytes(self):
        self.assertEqual(VADAudioSource.convert_data(b""), [])

    def test_single_byte(self):
        """Length < 2 returns empty list."""
        self.assertEqual(VADAudioSource.convert_data(b"\x01"), [])

    def test_odd_length_truncated(self):
        """Odd-length input is trimmed to even length."""
        result = VADAudioSource.convert_data(b"\x01\x02\x03")
        self.assertEqual(len(result), 1)

    def test_even_length(self):
        result = VADAudioSource.convert_data(b"\x01\x00\x02\x00")
        self.assertEqual(result, [1, 2])


# ---------------------------------------------------------------------------
# VAD path without frame_length (else branch in _process_chunk)
# ---------------------------------------------------------------------------


class TestVADWithoutFrameLength(unittest.TestCase):

    def test_process_chunk_no_frame_length(self):
        """VAD is called directly when frame_length is None."""
        source = FakeSource(chunks=[b"ab", b"cd"])
        stream = _make_stream(source)
        stream._vad.frame_length = None
        stream._vad.process.return_value = True

        result = list(stream.generator())
        self.assertTrue(len(result) > 0)


# ---------------------------------------------------------------------------
# Hotword detection mode
# ---------------------------------------------------------------------------


class TestHotwordDetectionMode(unittest.TestCase):

    @patch("voice_ui.speech_detection.vad_audio_source.VADFactory.create")
    @patch("voice_ui.speech_detection.vad_audio_source.HotwordDetector")
    def test_hotword_not_detected(self, mock_hw_cls, mock_vad_cls):
        mock_vad = MagicMock(frame_length=None)
        mock_vad_cls.return_value = MagicMock()
        mock_vad_cls.return_value.process.return_value = -1  # nothing detected
        mock_vad_cls.return_value.available_keywords.return_value = []
        mock_vad_cls.return_value = MagicMock()
        mock_vad_cls().process.return_value = -1

        source = FakeSource(chunks=[b"\x01\x02" * 160])
        stream = VADAudioSource(source_instance=source)
        stream._vad = mock_vad
        stream._detection_mode = VADAudioSource.DetectionMode.HOTWORD

        hotword_detector = MagicMock()
        hotword_detector.process.return_value = -1  # no detection
        hotword_detector.available_keywords.return_value = []
        stream._hotword_detector = hotword_detector

        list(stream.generator())

        self.assertIsNone(stream._last_hotword_detected)

    @patch("voice_ui.speech_detection.vad_audio_source.VADFactory.create")
    @patch("voice_ui.speech_detection.vad_audio_source.HotwordDetector")
    def test_hotword_detected_switches_to_vad(self, mock_hw_cls, mock_vad_cls):
        mock_vad = MagicMock(frame_length=None)
        mock_vad.process.return_value = True

        source = FakeSource(chunks=[b"\x01\x02" * 160, b"\x03\x04" * 160])
        stream = VADAudioSource(source_instance=source)
        stream._vad = mock_vad
        stream._detection_mode = VADAudioSource.DetectionMode.HOTWORD

        hotword_detector = MagicMock()
        hotword_detector.process.return_value = 0  # first keyword detected
        hotword_detector.available_keywords.return_value = ["hey_jarvis"]
        stream._hotword_detector = hotword_detector

        list(stream.generator())

        # After hotword, should have switched to VAD mode
        self.assertEqual(
            stream._detection_mode, VADAudioSource.DetectionMode.VOICE_ACTIVITY
        )
        self.assertEqual(stream._last_hotword_detected, "hey_jarvis")


# ---------------------------------------------------------------------------
# Generator edge cases
# ---------------------------------------------------------------------------


class TestGeneratorEdgeCases(unittest.TestCase):

    def test_generator_source_exception_returns_empty(self):
        """If source.generator() raises synchronously, the VAD generator yields nothing."""
        source = FakeSource()
        stream = _make_stream(source)
        # Replace generator with a regular function that raises immediately on call
        # (not inside the generator body, which would be lazy)
        stream._source.generator = MagicMock(
            side_effect=RuntimeError("generator error")
        )
        result = list(stream.generator())
        self.assertEqual(result, [])

    def test_generator_skips_none_chunks(self):
        """None chunks from source are skipped."""
        source = FakeSource()
        stream = _make_stream(source)

        # Manually push None into the generator sequence
        def gen_with_none():
            yield None
            yield b"\x01\x02" * 80

        stream._source = MagicMock()
        stream._source.generator.return_value = gen_with_none()
        stream._vad.process.return_value = False

        # Should not crash
        list(stream.generator())

    def test_generator_stops_when_closed(self):
        """Generator exits when _closed is set to True mid-stream."""
        stream = _make_stream(FakeSource())
        stream._vad.process.return_value = False

        def gen_sets_closed():
            stream._closed = True
            yield b"\x01\x02" * 80

        stream._source = MagicMock()
        stream._source.generator.return_value = gen_sets_closed()

        result = list(stream.generator())
        self.assertEqual(result, [])

    def test_generator_timeout_raises(self):
        """generator() raises TimeoutError when detection_timeout is exceeded."""
        from unittest.mock import patch
        from datetime import datetime, timedelta

        source = FakeSource(chunks=[b"\x01\x02" * 80])
        stream = _make_stream(source, detection_timeout=0.001)

        # Freeze time so it looks expired on first call
        past = datetime.now() - timedelta(seconds=10)
        with patch("voice_ui.speech_detection.vad_audio_source.datetime") as mock_dt:
            mock_dt.now.return_value = past + timedelta(seconds=10)
            mock_dt.now.side_effect = None
            # Simpler: just use the real timer but with a very short timeout
            stream._detection_timeout = 0.0
            with self.assertRaises(TimeoutError):
                list(stream.generator())

    def test_generator_yields_end_marker_when_speech_in_progress_at_end(self):
        """A trailing b'' is emitted if speech was active when source exhausted."""
        source = FakeSource(chunks=[b"ab"] * 5)
        stream = _make_stream(source)
        stream._vad.frame_length = None
        stream._vad.process.return_value = True  # always speech

        result = list(stream.generator())
        self.assertIn(b"", result)

    def test_speech_continues_yields_chunk(self):
        """When speech is already in progress, subsequent chunks are appended."""
        source = FakeSource(chunks=[b"ab", b"cd", b"ef"])
        stream = _make_stream(source)
        stream._vad.frame_length = None
        # First: speech starts; second: continues; third: ends
        stream._vad.process.side_effect = [True, True, False]

        result = list(stream.generator())
        # b"ab" (start of speech), b"cd" (continues), b"" (end marker)
        self.assertIn(b"cd", result)
        self.assertIn(b"", result)


class TestVADAudioSourceMiscCoverage(unittest.TestCase):

    def test_last_hotword_detected_property(self):
        """last_hotword_detected property returns the stored value."""
        source = FakeSource()
        stream = _make_stream(source)
        stream._last_hotword_detected = "hey_jarvis"
        self.assertEqual(stream.last_hotword_detected, "hey_jarvis")

    def test_process_chunk_unknown_detection_mode(self):
        """Else branch: detection_result=False when mode is neither VAD nor HOTWORD."""
        source = FakeSource(chunks=[b"ab"])
        stream = _make_stream(source)
        stream._vad.frame_length = None
        # Set to a value that matches neither DetectionMode branch
        stream._detection_mode = "UNKNOWN_MODE"
        # Should not raise; speech never detected
        result = list(stream.generator())
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()

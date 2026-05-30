import queue
import unittest
from unittest.mock import MagicMock, call, patch

import pyaudio

from voice_ui.audio_io.microphone import MicrophoneStream


class TestMicrophoneStream(unittest.TestCase):

    @patch("pyaudio.PyAudio")
    def setUp(self, mock_pyaudio):
        self.mock_pyaudio = mock_pyaudio
        self.stream = MicrophoneStream()

    def test_init(self):
        self.assertEqual(self.stream._rate, 16000)
        self.assertEqual(self.stream.rate, 16000)

        self.assertEqual(self.stream._chunk, 800)
        self.assertEqual(self.stream.chunk_size, 800)

        self.assertEqual(self.stream._channels, 1)
        self.assertEqual(self.stream.channels, 1)

        self.assertEqual(self.stream._sample_format, pyaudio.paInt16)
        self.assertEqual(self.stream.sample_format, pyaudio.paInt16)

        self.stream._audio_interface.get_sample_size = MagicMock(return_value=1234)
        self.assertEqual(self.stream.sample_size, 1234)
        self.stream._audio_interface.get_sample_size.assert_called_once_with(
            self.stream._sample_format
        )

        self.assertTrue(self.stream._closed)

    @patch.object(MicrophoneStream, "pause")
    @patch.object(MicrophoneStream, "resume")
    def test_context_manager(self, mock_resume, mock_pause):
        with self.stream:
            mock_resume.assert_called_once()
        mock_pause.assert_called_once()
        self.stream._audio_interface.terminate.assert_called_once()

    def test_fill_buffer(self):
        data = b"some random bytes"
        frame_count = 10
        time_info = None
        status_flags = None
        self.stream._fill_buffer(data, frame_count, time_info, status_flags)
        self.assertEqual(self.stream._buff.get(), data)

    def test_pause(self):
        self.stream.pause()
        self.assertTrue(self.stream._closed)
        self.stream._audio_stream.stop_stream.assert_called_once()

    def test_resume(self):
        self.stream.resume()
        self.assertFalse(self.stream._closed)
        self.stream._audio_stream.start_stream.assert_called_once()

    def test_yield_bytes(self):
        data = b"1234567890"
        byte_limit = 5
        result = list(self.stream._yield_bytes(data, byte_limit))
        self.assertEqual(result, [b"12345", b"67890"])

    def test_generator(self):
        self.stream._yield_bytes = MagicMock()

        self.stream._buff.get = MagicMock(
            side_effect=[b"123", b"456", b"789", queue.Empty(), None]
        )

        self.stream._closed = False

        list(self.stream.generator())

        self.stream._buff.get.assert_has_calls(
            [call(), call(block=False), call(block=False), call(block=False)]
        )
        self.stream._yield_bytes.assert_called_once_with(b"123456789", 25000)

    def test_generator_interrupted(self):
        self.stream._yield_bytes = MagicMock()

        self.stream._buff.get = MagicMock(side_effect=[b"123", b"456", None, b"789"])

        self.stream._closed = False

        list(self.stream.generator())

        self.stream._buff.get.assert_has_calls(
            [call(), call(block=False), call(block=False)]
        )
        self.stream._yield_bytes.assert_not_called()


if __name__ == "__main__":
    unittest.main()

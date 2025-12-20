import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from voice_ui.voice_activity_detection.vad_silero import SileroVAD


class TestSileroVAD(unittest.TestCase):
    @patch("silero_vad.load_silero_vad")
    def setUp(self, mock_silero_load):
        self.mock_silero = MagicMock()
        mock_silero_load.return_value = self.mock_silero

        self.vad = SileroVAD()

        self.cache = {}
        mock_silero_load.assert_called_once_with(onnx=True)
        self.assertEqual(self.mock_silero, self.vad._vad_model)

    def test_initialization(self):
        self.assertEqual(self.vad.frame_length, 512)
        self.assertEqual(self.vad.sample_rate, 16_000)

    def test_convert_data_to_numpy_array(self):
        # Create sample audio data
        test_data = np.array([1000, -1000], dtype=np.int16).tobytes()
        result = self.vad._convert_data_to_numpy_array(test_data)

        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(len(result), 2)
        self.assertTrue(np.all(np.abs(result) <= 1.0))  # Check normalization

    @patch("silero_vad.VADIterator")
    def test_process_with_bytes(self, mock_vad_iterator_constructor):
        # Create sample audio data
        test_data = np.zeros(1600, dtype=np.int16).tobytes()
        mock_vad_iterator = MagicMock()
        mock_vad_iterator_constructor.return_value = mock_vad_iterator

        result = self.vad.process(test_data, self.cache)

        self.assertIsInstance(result, bool)
        mock_vad_iterator_constructor.assert_called_once_with(
            self.mock_silero,
            threshold=0.5,
            speech_pad_ms=0.1 * 1000,
            min_silence_duration_ms=0.5 * 1000,
        )
        mock_vad_iterator.assert_called_once()

    @patch("silero_vad.VADIterator")
    def test_process_with_list(self, mock_vad_iterator_constructor):
        # Create sample audio data as list
        test_data = [0.0] * 1600
        mock_vad_iterator = MagicMock()
        mock_vad_iterator_constructor.return_value = mock_vad_iterator

        result = self.vad.process(test_data, self.cache)

        self.assertIsInstance(result, bool)
        mock_vad_iterator_constructor.assert_called_once_with(
            self.mock_silero,
            threshold=0.5,
            speech_pad_ms=0.1 * 1000,
            min_silence_duration_ms=0.5 * 1000,
        )
        mock_vad_iterator.assert_called_once()

    def test_process_invalid_data_type(self):
        with self.assertRaises(ValueError):
            self.vad.process(123, self.cache)  # Invalid data type

    def test_process_without_cache(self):
        test_data = np.zeros(1600, dtype=np.int16).tobytes()
        with self.assertRaises(ValueError):
            self.vad.process(test_data, None)

    def test_chunk_size_default(self):
        test_data = np.zeros(1600, dtype=np.int16).tobytes()
        mock_vad_iterator = MagicMock()
        self.cache["vad_iterator"] = mock_vad_iterator

        result = self.vad.process(test_data, self.cache, chunk_size=None)
        self.assertIsInstance(result, bool)
        mock_vad_iterator.assert_called_once()

    def test_chunk_size_custom(self):
        test_data = np.zeros(1600, dtype=np.int16).tobytes()
        mock_vad_iterator = MagicMock()
        self.cache["vad_iterator"] = mock_vad_iterator

        result = self.vad.process(test_data, self.cache, chunk_size=100)
        self.assertIsInstance(result, bool)
        mock_vad_iterator.assert_called_once()

    def test_process_speech_started(self):
        test_data = np.zeros(1600, dtype=np.int16).tobytes()

        mock_vad_iterator = MagicMock(return_value={"start": 1234})
        self.cache["vad_iterator"] = mock_vad_iterator
        self.cache["speech_detected"] = False

        result = self.vad.process(test_data, self.cache)
        self.assertTrue(result)
        self.assertTrue(self.cache["speech_detected"])
        mock_vad_iterator.assert_called_once()

    def test_process_speech_stopped(self):
        test_data = np.zeros(1600, dtype=np.int16).tobytes()

        mock_vad_iterator = MagicMock(return_value={"end": 2345})
        self.cache["vad_iterator"] = mock_vad_iterator
        self.cache["speech_detected"] = False

        result = self.vad.process(test_data, self.cache)
        self.assertFalse(result)
        self.assertFalse(self.cache["speech_detected"])
        mock_vad_iterator.assert_called_once()

    def test_process_speech_not_in_progress_no_start(self):
        test_data = np.zeros(1600, dtype=np.int16).tobytes()

        mock_vad_iterator = MagicMock(return_value=None)
        self.cache["vad_iterator"] = mock_vad_iterator
        self.cache["speech_detected"] = False

        result = self.vad.process(test_data, self.cache)
        self.assertFalse(result)  # The same as speech_detected
        self.assertFalse(self.cache["speech_detected"])
        mock_vad_iterator.assert_called_once()

    def test_process_speech_detected_no_stop(self):
        test_data = np.zeros(1600, dtype=np.int16).tobytes()

        mock_vad_iterator = MagicMock(return_value=None)
        self.cache["vad_iterator"] = mock_vad_iterator
        self.cache["speech_detected"] = True

        result = self.vad.process(test_data, self.cache)
        self.assertTrue(result)  # The same as speech_detected
        self.assertTrue(self.cache["speech_detected"])
        mock_vad_iterator.assert_called_once()


if __name__ == "__main__":
    unittest.main()

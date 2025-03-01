import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from voice_ui.voice_activity_detection.vad_funasr import FunASRVAD


class TestFunASRVAD(unittest.TestCase):
    @patch('funasr.AutoModel')
    def setUp(self, mock_funasr_automodel):
        self.mock_funasr = MagicMock()
        mock_funasr_automodel.return_value = self.mock_funasr

        self.vad = FunASRVAD(frame_length_ms=200)

        self.cache = {}
        mock_funasr_automodel.assert_called_once_with(model="fsmn-vad", disable_update=True)
        self.assertEqual(self.mock_funasr, self.vad._vad)

    def test_initialization(self):
        self.assertEqual(self.vad._frame_length_ms, 200)
        self.assertEqual(self.vad.sample_rate, 16000)
        self.assertEqual(self.vad.frame_length, 3200)  # 200ms * 16000Hz / 1000

    def test_convert_data_to_numpy_array(self):
        # Create sample audio data
        test_data = np.array([1000, -1000], dtype=np.int16).tobytes()
        result = self.vad._convert_data_to_numpy_array(test_data)

        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(len(result), 2)
        self.assertTrue(np.all(np.abs(result) <= 1.0))  # Check normalization

    def test_process_with_bytes(self):
        # Create sample audio data
        test_data = np.zeros(1600, dtype=np.int16).tobytes()
        result = self.vad.process(test_data, self.cache)
        self.assertIsInstance(result, bool)

    def test_process_with_list(self):
        # Create sample audio data as list
        test_data = [0.0] * 1600
        result = self.vad.process(test_data, self.cache)
        self.assertIsInstance(result, bool)

    def test_process_invalid_data_type(self):
        with self.assertRaises(ValueError):
            self.vad.process(123, self.cache)  # Invalid data type

    def test_process_without_cache(self):
        test_data = np.zeros(1600, dtype=np.int16).tobytes()
        with self.assertRaises(ValueError):
            self.vad.process(test_data, None)

    def test_chunk_size_default(self):
        test_data = np.zeros(1600, dtype=np.int16).tobytes()
        result = self.vad.process(test_data, self.cache, chunk_size=None)
        self.assertIsInstance(result, bool)

    def test_chunk_size_custom(self):
        test_data = np.zeros(1600, dtype=np.int16).tobytes()
        result = self.vad.process(test_data, self.cache, chunk_size=100)
        self.assertIsInstance(result, bool)

    def test_process_speech_started(self):
        test_data = np.zeros(1600, dtype=np.int16).tobytes()
        self.mock_funasr.generate.return_value = [{'key': 'rand_value', 'value': [[1234, -1]]}]
        self.cache['speech_in_progress'] = False

        result = self.vad.process(test_data, self.cache)
        self.assertTrue(result)
        self.assertTrue(self.cache['speech_in_progress'])

    def test_process_speech_stopped(self):
        test_data = np.zeros(1600, dtype=np.int16).tobytes()
        self.mock_funasr.generate.return_value = [{'key': 'rand_value', 'value': [[-1, 2345]]}]
        self.cache['speech_in_progress'] = True

        result = self.vad.process(test_data, self.cache)
        self.assertTrue(result)
        self.assertFalse(self.cache['speech_in_progress'])

    def test_process_speech_not_in_progress_no_start(self):
        test_data = np.zeros(1600, dtype=np.int16).tobytes()
        self.mock_funasr.generate.return_value = [{'key': 'rand_value', 'value': []}]
        self.cache['speech_in_progress'] = False

        result = self.vad.process(test_data, self.cache)
        self.assertFalse(result)  # The same as speech_in_progress
        self.assertFalse(self.cache['speech_in_progress'])

    def test_process_speech_in_progress_no_stop(self):
        test_data = np.zeros(1600, dtype=np.int16).tobytes()
        self.mock_funasr.generate.return_value = [{'key': 'rand_value', 'value': []}]
        self.cache['speech_in_progress'] = True

        result = self.vad.process(test_data, self.cache)
        self.assertTrue(result)  # The same as speech_in_progress
        self.assertTrue(self.cache['speech_in_progress'])


if __name__ == '__main__':
    unittest.main()

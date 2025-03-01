import os
import struct
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from voice_ui.voice_activity_detection.vad_picovoice import PicoVoiceVAD


class TestPicoVoiceVAD(unittest.TestCase):
    @patch('pvcobra.create')
    def setUp(self, mock_create):
        # Mock the cobra object
        self.mock_cobra = MagicMock()
        self.mock_cobra.frame_length = 512
        self.mock_cobra.sample_rate = 16000
        mock_create.return_value = self.mock_cobra

        # Set environment variable for testing
        os.environ['PORCUPINE_ACCESS_KEY'] = 'test-key'

        self.vad = PicoVoiceVAD()
        self.cache = {}

    def test_initialization(self):
        self.assertEqual(self.vad.frame_length, 512)
        self.assertEqual(self.vad.sample_rate, 16000)

    def test_convert_data(self):
        # Create test data
        test_values = [1000, -1000, 500, -500]
        byte_data = struct.pack(f"{len(test_values)}h", *test_values)

        result = self.vad._convert_data(byte_data)
        self.assertEqual(result, test_values)

    def test_convert_duration_to_chunks(self):
        # Test with 1 second duration
        chunks = self.vad._convert_duration_to_chunks(1.0)
        expected_chunks = int(np.ceil(16000 / 512))  # sample_rate / frame_length
        self.assertEqual(chunks, expected_chunks)

    def test_create_cache(self):
        test_cache = {}
        start_chunks = 5
        self.vad._create_cache(test_cache, start_chunks)

        self.assertIn("processed_audio_length_ms", test_cache)
        self.assertIn("threshold_counter", test_cache)
        self.assertIn("above_threshold_counter", test_cache)
        self.assertIn("below_threshold_counter", test_cache)
        self.assertIn("speech_detected", test_cache)

    def test_process_with_bytes(self):
        # Create sample audio data
        test_data = struct.pack("512h", *([0] * 512))
        self.mock_cobra.process.return_value = 0.5

        result = self.vad.process(
            test_data,
            self.cache,
            threshold=0.7,
            pre_speech_duration=0.2,
            post_speech_duration=1.0
        )
        self.assertIsInstance(result, bool)

    def test_process_with_list(self):
        test_data = [0] * 512
        self.mock_cobra.process.return_value = 0.8

        result = self.vad.process(
            test_data,
            self.cache,
            threshold=0.7
        )
        self.assertIsInstance(result, bool)

    def test_process_invalid_data_type(self):
        with self.assertRaises(ValueError):
            self.vad.process(123, self.cache)

    def test_process_without_cache(self):
        test_data = [0] * 512
        with self.assertRaises(ValueError):
            self.vad.process(test_data, None)

    def test_speech_detection_threshold(self):
        test_data = [0] * 512
        self.mock_cobra.process.return_value = 0.9  # High probability

        # Process multiple frames to trigger speech detection
        for _ in range(5):
            self.vad.process(
                test_data,
                self.cache,
                threshold=0.7,
                pre_speech_duration=0.1
            )

        self.assertTrue(self.cache["speech_detected"])

    def test_speech_end_detection(self):
        test_data = [0] * 512
        self.mock_cobra.process.return_value = 0.9

        # First detect speech
        for _ in range(5):
            self.vad.process(test_data, self.cache, threshold=0.7)

        # Then simulate silence
        self.mock_cobra.process.return_value = 0.1
        for _ in range(20):
            self.vad.process(test_data, self.cache, threshold=0.7)

        self.assertFalse(self.cache["speech_detected"])

    def tearDown(self):
        self.vad.__del__()


if __name__ == '__main__':
    unittest.main()

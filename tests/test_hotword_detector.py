import os
import unittest
from typing import KeysView
from unittest.mock import MagicMock, call, patch

from voice_ui.speech_detection.hotword_detector import HotwordDetector


class TestHotwordDetector(unittest.TestCase):

    @patch('pvporcupine.create')
    def setUp(self, mock_create):
        mock_create.return_value = MagicMock(frame_length=512)
        os.environ['PORCUPINE_ACCESS_KEY'] = '1234'
        self.detector = HotwordDetector()
        self.mock_create = mock_create

    def test_init_with_default_keywords(self):
        self.assertEqual(self.detector._handle, self.mock_create.return_value)
        self.mock_create.assert_called_once()

    @patch('os.path.exists')
    @patch('os.path.abspath', return_value='mock_path')
    def test_available_keyword_paths(self, mock_abspath, mock_path_exists):
        mock_path_exists.return_value = True

        self.detector._additional_keyword_paths = {
            'selena': '/some/resources/dir/Selena_en_raspberry-pi_v3_0_0.ppn',
            'artemis': '/some/resources/dir/Artemis_en_raspberry-pi_v3_0_0.ppn'
        }

        keyword_paths = self.detector.available_keyword_paths()

        self.assertEqual(mock_path_exists.call_count, 2)
        mock_path_exists.assert_has_calls([
            call('/some/resources/dir/Selena_en_raspberry-pi_v3_0_0.ppn'),
            call('/some/resources/dir/Artemis_en_raspberry-pi_v3_0_0.ppn'),
        ])
        self.assertIn('selena', keyword_paths)
        self.assertEqual(keyword_paths['selena'], 'mock_path')

    def test_available_keywords(self):
        keywords = self.detector.available_keywords()
        self.assertIsInstance(keywords, KeysView)

    def test_process_with_incorrect_audio_frame_length(self):
        incorrect_audio_frame = [0] * (self.detector._handle.frame_length // 2)

        self.detector._handle.process.return_value = 3

        result = self.detector.process(incorrect_audio_frame)

        self.detector._handle.process.assert_not_called()
        self.assertEqual(result, -1)

    def test_process_with_correct_audio_frame_length(self):
        correct_audio_frame = [0] * self.detector._handle.frame_length

        self.detector._handle.process.return_value = 1

        result = self.detector.process(correct_audio_frame)

        self.detector._handle.process.assert_called_once()
        self.assertEqual(result, 1)

    def test_process_with_correct_multiple_frames_no_speaker_detected(self):
        audio_frame1 = [1] * self.detector._handle.frame_length
        audio_frame2 = [2] * self.detector._handle.frame_length
        audio_frame3 = [3] * self.detector._handle.frame_length

        self.detector._handle.process.side_effect = [-1, -1, -1]

        result = self.detector.process(audio_frame1 + audio_frame2 + audio_frame3)

        self.assertEqual(result, -1)
        self.detector._handle.process.assert_has_calls([
            call(audio_frame1),
            call(audio_frame2),
            call(audio_frame3),
        ])

    def test_process_with_correct_multiple_frames_speaker_detected(self):
        audio_frame1 = [4] * self.detector._handle.frame_length
        audio_frame2 = [5] * self.detector._handle.frame_length
        audio_frame3 = [6] * self.detector._handle.frame_length

        self.detector._handle.process.side_effect = [-1, 2]

        result = self.detector.process(audio_frame1 + audio_frame2 + audio_frame3)

        self.assertEqual(result, 2)
        self.detector._handle.process.assert_has_calls([
            call(audio_frame1),
            call(audio_frame2),
        ])


if __name__ == '__main__':
    unittest.main()

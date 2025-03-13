import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, mock_open, patch

from voice_ui.speech_detection.speaker_profile_manager import SpeakerProfileManager


class TestSpeakerProfileManager(unittest.TestCase):

    @patch('os.environ', {'PORCUPINE_ACCESS_KEY': 'test_key'})
    @patch('pveagle.create_recognizer')
    @patch('pathlib.Path.exists', return_value=True)
    def setUp(self, mock_exists, mock_eagle_recognizer):
        self.profile_dir = Path('/fake/dir')
        self.manager = SpeakerProfileManager(self.profile_dir)

        mock_eagle_recognizer.assert_called_once()

    @patch('pathlib.Path.exists', return_value=False)
    def test_init_path_does_not_exist(self, mock_exists):
        with self.assertRaises(FileNotFoundError):
            self.manager = SpeakerProfileManager(self.profile_dir)

    @patch('os.environ', {'PORCUPINE_ACCESS_KEY': 'test_key'})
    @patch('pveagle.create_profiler')
    @patch('pathlib.Path.exists', return_value=False)
    def test_create_profile_success(self, mock_exists, mock_create_profiler):
        self.mock_eagle_profiler = mock_create_profiler.return_value

        with patch('pvrecorder.PvRecorder') as MockPvRecorder:
            mock_recorder = MockPvRecorder.return_value
            self.mock_eagle_profiler.min_enroll_samples = 512
            self.mock_eagle_profiler.enroll.side_effect = [(50.0, None), (75.0, None), (100.0, None), (100.0, None), KeyboardInterrupt]
            self.mock_eagle_profiler.export.return_value.to_bytes.return_value = b'test_data'

            m_open = mock_open()
            with patch('builtins.open', m_open):
                self.manager.create_profile('test_profile')

            mock_recorder.start.assert_called_once()
            mock_recorder.read.assert_called()
            mock_recorder.stop.assert_called_once()
            mock_recorder.delete.assert_called_once()
            self.mock_eagle_profiler.delete.assert_called_once()

            m_open.assert_called_with(self.profile_dir / 'test_profile.bin', 'wb')
            m_open().write.assert_called_once_with(b'test_data')

    @patch('pathlib.Path.exists', return_value=True)
    def test_create_profile_exists(self, mock_exists):
        with self.assertRaises(FileExistsError):
            self.manager.create_profile('test_profile')

    def test_profiles(self):
        self.manager._speaker_profiles = [{"name": "profile1", "profile_data": b"\x00\x01"}, {"name": "profile2", "profile_data": b"\x02\x03"}]
        self.assertEqual(self.manager.profiles, ['profile1', 'profile2'])

    @patch('os.environ', {'PORCUPINE_ACCESS_KEY': 'test_key'})
    @patch('pveagle.create_recognizer')
    def test_load_profiles(self, mock_eagle_recognizer):
        profile_data = b'test_data'
        mock_files = [Path('/fake/dir/profile1.bin'), Path('/fake/dir/profile2.bin')]

        m_open = mock_open(read_data=profile_data)
        with patch('builtins.open', m_open):
            with patch('pathlib.Path.glob', return_value=mock_files):
                with patch('pveagle.EagleProfile.from_bytes') as mock_from_bytes:
                    self.manager.load_profiles()

        self.assertEqual(len(self.manager._speaker_profiles), 2)
        self.assertEqual(self.manager._speaker_profiles[0]['name'], 'profile1')
        self.assertEqual(self.manager._speaker_profiles[1]['name'], 'profile2')
        mock_from_bytes.assert_called_with(profile_data)
        mock_eagle_recognizer.assert_called_once()


class TestSpeakerProfileSpeakerIdentification(unittest.TestCase):
    @patch('os.environ', {'PORCUPINE_ACCESS_KEY': 'test_key'})
    @patch('pveagle.create_recognizer')
    @patch('pathlib.Path.exists', return_value=True)
    def setUp(self, mock_exists, mock_eagle_recognizer):
        self.profile_dir = Path('/fake/dir')
        self.manager = SpeakerProfileManager(self.profile_dir)

        self.manager._speaker_profiles = [
            {"name": "Speaker1", "profile_data": b"\x00\x01"},
            {"name": "Speaker2", "profile_data": b"\x02\x03"},
            {"name": "Speaker3", "profile_data": b"\x04\x05"},
        ]
        self.manager._eagle_recognizer = MagicMock(frame_length=512)

        mock_eagle_recognizer.assert_called_once()

    def test_detect_speaker_with_valid_single_frame(self):
        expected_scores = [0.0, 0.0, 0.95]
        self.manager._eagle_recognizer.process.return_value = expected_scores

        audio_frame = [0] * 512
        result = self.manager.detect_speaker(audio_frame)

        self.assertEqual(result, expected_scores)
        self.manager._eagle_recognizer.process.assert_called_once_with(audio_frame)

    def test_detect_speaker_with_valid_multiple_frames(self):
        self.manager._eagle_recognizer.process.side_effect = [
            [0, 1, 2],
            [3, 4, 5],
            [6, 7, 8],
        ]
        expected_scores = [3, 4, 5]  # This is the average of the three frames scores.

        audio_frame1 = [1] * 512
        audio_frame2 = [2] * 512
        audio_frame3 = [3] * 512

        result = self.manager.detect_speaker(audio_frame1 + audio_frame2 + audio_frame3)

        self.assertEqual(result, expected_scores)
        self.manager._eagle_recognizer.process.assert_has_calls([
            call(audio_frame1),
            call(audio_frame2),
            call(audio_frame3),
        ])

    def test_detect_speaker_with_valid_multiple_incomplete_frames(self):
        self.manager._eagle_recognizer.process.side_effect = [
            [0, 1, 2],
            [3, 4, 5],
            [6, 7, 8],
        ]
        expected_scores = [1.5, 2.5, 3.5]  # This is the average of the two frames scores.

        audio_frame1 = [1] * 512
        audio_frame2 = [2] * 512
        audio_frame3 = [3] * 256  # Shorter than frame_length

        result = self.manager.detect_speaker(audio_frame1 + audio_frame2 + audio_frame3)

        self.assertEqual(result, expected_scores)
        self.manager._eagle_recognizer.process.assert_has_calls([
            call(audio_frame1),
            call(audio_frame2),
        ])

    def test_detect_speaker_with_no_recognizer(self):
        self.manager._eagle_recognizer = None
        audio_frame = [0] * 512

        with self.assertLogs(level='ERROR') as log:
            result = self.manager.detect_speaker(audio_frame)

        self.assertIsNone(result)
        self.assertIn("Eagle recognizer is not initialized", log.output[0])

    def test_detect_speaker_with_no_detection(self):
        audio_frame = [0] * 512
        self.manager._eagle_recognizer.process.return_value = None

        with self.assertLogs(level='DEBUG') as log:
            result = self.manager.detect_speaker(audio_frame)

        self.assertIsNone(result)
        self.assertIn("No speaker detected", log.output[0])
        self.manager._eagle_recognizer.process.assert_called_once_with(audio_frame)

    def test_get_speaker_name_empty_scores(self):
        result = self.manager.get_speaker_name([])
        self.assertIsNone(result)

    def test_get_speaker_name_below_threshold(self):
        scores = [0.1, 0.15, 0.19]
        result = self.manager.get_speaker_name(scores)
        self.assertIsNone(result)

    def test_get_speaker_name_valid_score(self):
        scores = [0.3, 0.8, 0.5]
        result = self.manager.get_speaker_name(scores)
        expected = {
            "name": "Speaker2",
            "id": 1,
            "score": 0.8
        }
        self.assertEqual(result, expected)

    def test_get_speaker_name_multiple_speakers_same_score(self):
        scores = [0.9, 0.9, 0.5]
        result = self.manager.get_speaker_name(scores)
        expected = {
            "name": "Speaker1",
            "id": 0,
            "score": 0.9
        }
        self.assertEqual(result, expected)

    def test_get_speaker_name_threshold_exact(self):
        scores = [0.2, 0.1, 0.15]
        result = self.manager.get_speaker_name(scores)
        expected = {
            "name": "Speaker1",
            "id": 0,
            "score": 0.2
        }
        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()

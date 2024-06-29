import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

from voice_ui.speech_recognition.speaker_profile_manager import SpeakerProfileManager


class TestSpeakerProfileManager(unittest.TestCase):

    @patch('pathlib.Path.exists', return_value=True)
    def setUp(self, mock_exists):
        self.profile_dir = Path('/fake/dir')
        self.manager = SpeakerProfileManager(self.profile_dir)

    @patch('pathlib.Path.exists', return_value=False)
    def test_init_path_does_not_exist(self, mock_exists):
        self.profile_dir = Path('/fake/dir')

        with self.assertRaises(ValueError):
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

    @patch('pathlib.Path.exists', return_value=True)
    def test_list_profiles(self, mock_exists):
        with patch('pathlib.Path.glob', return_value=[Path('/fake/dir/profile1.bin'), Path('/fake/dir/profile2.bin')]):
            profiles = self.manager.list_profiles()
            self.assertEqual(profiles, ['profile1', 'profile2'])

    @patch('pathlib.Path.exists', return_value=True)
    def test_load_profiles(self, mock_exists):
        profile_data = b'test_data'
        mock_files = [Path('/fake/dir/profile1.bin'), Path('/fake/dir/profile2.bin')]

        m_open = mock_open(read_data=profile_data)
        with patch('builtins.open', m_open):
            with patch('pathlib.Path.glob', return_value=mock_files):
                with patch('pveagle.EagleProfile.from_bytes') as mock_from_bytes:
                    profiles = self.manager.load_profiles()

            self.assertEqual(len(profiles), 2)
            self.assertEqual(profiles[0]['name'], 'profile1')
            self.assertEqual(profiles[1]['name'], 'profile2')
            mock_from_bytes.assert_called_with(profile_data)

    @patch('pathlib.Path.exists', return_value=False)
    def test_load_profiles_directory_not_exist(self, mock_exists):
        with self.assertRaises(FileNotFoundError):
            self.manager.load_profiles()


if __name__ == '__main__':
    unittest.main()

import queue
import unittest
from unittest.mock import MagicMock, patch

import requests

from voice_ui.audio_io.player import Player
from voice_ui.speech_synthesis.openai_text_to_speech_streamer import (
    OpenAITextToSpeechAudioStreamer,
)


def player_init(self):
    self._stream = MagicMock()
    self._audio_interface = MagicMock()


class TestWhisperTextToSpeechAudioStreamer(unittest.TestCase):

    @patch('threading.Thread')
    @patch.object(Player, '__init__', new=player_init)
    def setUp(self, mock_thread):
        self.streamer = OpenAITextToSpeechAudioStreamer()

        self.streamer._player = MagicMock()

        # mock_player_init.assert_called_once()
        mock_thread.return_value.start.assert_called_once()

    def tearDown(self):
        del self.streamer

    def test_initialization(self):
        self.assertFalse(self.streamer.is_stopped())
        self.assertFalse(self.streamer.is_speaking())

    def test_stop(self):
        self.streamer.stop()
        self.assertTrue(self.streamer.is_stopped())

    def test_speaker_plays_audio_data(self):
        test_data = b'test audio data'

        def audio_bytes_queue_side_effect(timeout):
            if self.streamer._data_queue.get.call_count > 1:
                self.streamer._terminated = True
                raise queue.Empty
            return test_data

        self.streamer._data_queue = MagicMock()
        self.streamer._data_queue.get.side_effect = audio_bytes_queue_side_effect

        self.streamer._speaker_thread_function()

        self.streamer._player.play_data.assert_called_once()

        self.streamer.stop()
        self.assertEqual(self.streamer._data_queue.get.call_count, 2)
        self.assertFalse(self.streamer.is_speaking())

    def test_speaker_handles_exceptions_during_playback(self):
        test_data = b'test audio data'

        def audio_bytes_queue_side_effect(timeout):
            if self.streamer._data_queue.get.call_count > 1:
                self.streamer._terminated = True
                raise queue.Empty
            return test_data

        self.streamer._data_queue = MagicMock()
        self.streamer._data_queue.get.side_effect = audio_bytes_queue_side_effect

        self.streamer._player.play_data.side_effect = Exception("Test exception")

        self.streamer._speaker_thread_function()

        self.streamer._player.play_data.assert_called_once()

        self.streamer.stop()
        self.assertEqual(self.streamer._data_queue.get.call_count, 2)
        self.assertFalse(self.streamer.is_speaking())

    def test_available_voices(self):
        voices = self.streamer.available_voices()
        expected_voices = [
            {'name': self.streamer.Voice.ALLOY, 'gender': 'NEUTRAL'},
            {'name': self.streamer.Voice.ECHO, 'gender': 'MALE'},
            {'name': self.streamer.Voice.FABLE, 'gender': 'NEUTRAL'},
            {'name': self.streamer.Voice.ONYX, 'gender': 'MALE'},
            {'name': self.streamer.Voice.NOVA, 'gender': 'FEMALE'},
            {'name': self.streamer.Voice.SHIMMER, 'gender': 'FEMALE'},
        ]
        self.assertEqual(voices, expected_voices)

    @patch('os.environ', {"OPENAI_API_KEY": 'test_key'})
    @patch('requests.post')
    def test_speak_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.raw = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        self.streamer._data_queue = MagicMock()

        with patch('wave.open') as mock_wave:
            mock_wave.return_value.__enter__.return_value.readframes.side_effect = [b'test_data', b'']

            self.streamer.speak("Hello world")

        self.assertFalse(self.streamer.is_stopped())
        mock_post.assert_called_once()
        mock_response.raise_for_status.assert_called_once()
        self.streamer._data_queue.put.assert_called_once_with(b'test_data')

    @patch('os.environ', {"OPENAI_API_KEY": 'test_key'})
    @patch('requests.post')
    def test_speak_http_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("HTTP Error")
        mock_post.return_value = mock_response

        text_queue = queue.Queue()
        self.streamer.speak("Hello world", text_queue)

        self.assertFalse(self.streamer.is_stopped())
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(mock_response.raise_for_status.call_count, 2)


if __name__ == '__main__':
    unittest.main()

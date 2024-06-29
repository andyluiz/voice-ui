import queue
import unittest
from unittest.mock import MagicMock, patch

import requests
from voice_ui.speech_synthesis.player import Player
from voice_ui.speech_synthesis.text_to_speech_streamer import TextToSpeechAudioStreamer


class TestTextToSpeechAudioStreamer(unittest.TestCase):

    @patch('threading.Thread')
    def setUp(self, mock_thread):
        self.streamer = TextToSpeechAudioStreamer()

        mock_thread.return_value.start.assert_called_once()

    def tearDown(self):
        del self.streamer

    def test_initialization(self):
        self.assertFalse(self.streamer.is_stopped())
        self.assertFalse(self.streamer.is_speaking())

    def test_stop(self):
        self.streamer.stop()
        self.assertTrue(self.streamer.is_stopped())

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
    def test_transcribe_to_stream_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.raw = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        text_queue = MagicMock()

        with patch('wave.open') as mock_wave:
            mock_wave.return_value.__enter__.return_value.readframes.side_effect = [b'test_data', b'']

            self.streamer.transcribe_to_stream("Hello world", text_queue)

        self.assertFalse(self.streamer.is_stopped())
        mock_post.assert_called_once()
        mock_response.raise_for_status.assert_called_once()
        text_queue.put.assert_called_once_with(b'test_data')

    @patch('os.environ', {"OPENAI_API_KEY": 'test_key'})
    @patch('requests.post')
    def test_transcribe_to_stream_http_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("HTTP Error")
        mock_post.return_value = mock_response

        text_queue = queue.Queue()
        self.streamer.transcribe_to_stream("Hello world", text_queue)

        self.assertFalse(self.streamer.is_stopped())
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(mock_response.raise_for_status.call_count, 2)

    @patch.object(Player, '__new__', return_value=MagicMock())
    def test_speaker_plays_audio_data(self, mock_player_new):
        test_data = b'test audio data'

        def audio_bytes_queue_side_effect(timeout):
            if self.streamer._audio_bytes_queue.get.call_count > 1:
                self.streamer._terminated = True
                raise queue.Empty
            return test_data

        self.streamer._audio_bytes_queue = MagicMock()
        self.streamer._audio_bytes_queue.get.side_effect = audio_bytes_queue_side_effect

        self.streamer._speaker()

        mock_player_new.return_value.play_data.assert_called_once()

        self.streamer.stop()
        self.assertEqual(self.streamer._audio_bytes_queue.get.call_count, 2)
        self.assertFalse(self.streamer.is_speaking())

    @patch.object(Player, '__new__', return_value=MagicMock())
    def test_speaker_handles_exceptions_during_playback(self, mock_player_new):
        test_data = b'test audio data'

        def audio_bytes_queue_side_effect(timeout):
            if self.streamer._audio_bytes_queue.get.call_count > 1:
                self.streamer._terminated = True
                raise queue.Empty
            return test_data

        self.streamer._audio_bytes_queue = MagicMock()
        self.streamer._audio_bytes_queue.get.side_effect = audio_bytes_queue_side_effect

        mock_player_new.return_value.play_data.side_effect = Exception("Test exception")

        self.streamer._speaker()

        mock_player_new.return_value.play_data.assert_called_once()

        self.streamer.stop()
        self.assertEqual(self.streamer._audio_bytes_queue.get.call_count, 2)
        self.assertFalse(self.streamer.is_speaking())

    def test_speak(self):
        self.streamer.transcribe_to_stream = MagicMock(return_value='I have spoken')

        result = self.streamer.speak(
            text="Hello world",
            voice=self.streamer.Voice.ALLOY,
            response_format='test_format',
            extra_param1='test_param1',
            extra_param2='test_param2',
        )

        self.streamer.transcribe_to_stream.assert_called_once_with(
            text="Hello world",
            stream=self.streamer._audio_bytes_queue,
            voice=self.streamer.Voice.ALLOY,
            response_format='test_format',
            extra_param1='test_param1',
            extra_param2='test_param2',
        )

        self.assertEqual(result, 'I have spoken')


if __name__ == '__main__':
    unittest.main()

import queue
import unittest
from unittest.mock import MagicMock, patch

import requests

from voice_ui.audio_io.player import Player
from voice_ui.speech_synthesis.openai_text_to_speech_streamer import (
    OpenAITextToSpeechAudioStreamer,
)


def player_init(self):
    self._audio_stream = MagicMock()
    self._audio_interface = MagicMock()


class TestWhisperTextToSpeechAudioStreamer(unittest.TestCase):

    @patch("threading.Thread")
    @patch.object(Player, "__init__", new=player_init)
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

    def test_available_voices(self):
        voices = self.streamer.available_voices()
        expected_voices = [
            {"name": self.streamer.Voice.ALLOY, "gender": "FEMALE"},
            {"name": self.streamer.Voice.ASH, "gender": "MALE"},
            {"name": self.streamer.Voice.BALLAD, "gender": "NEUTRAL"},
            {"name": self.streamer.Voice.CORAL, "gender": "FEMALE"},
            {"name": self.streamer.Voice.ECHO, "gender": "MALE"},
            {"name": self.streamer.Voice.FABLE, "gender": "NEUTRAL"},
            {"name": self.streamer.Voice.ONYX, "gender": "MALE"},
            {"name": self.streamer.Voice.NOVA, "gender": "FEMALE"},
            {"name": self.streamer.Voice.SAGE, "gender": "FEMALE"},
            {"name": self.streamer.Voice.SHIMMER, "gender": "FEMALE"},
            {"name": self.streamer.Voice.VERSE, "gender": "MALE"},
        ]
        self.assertEqual(voices, expected_voices)

    @patch("os.environ", {"OPENAI_API_KEY": "test_key"})
    @patch("requests.post")
    def test_speak_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.raw = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with patch("wave.open") as mock_wave:
            mock_wave.return_value.__enter__.return_value.readframes.side_effect = [
                b"test_data",
                b"",
            ]

            self.streamer.speak("Hello world")

        self.assertFalse(self.streamer.is_stopped())
        mock_post.assert_called_once()
        mock_response.raise_for_status.assert_called_once()

    @patch("os.environ", {"OPENAI_API_KEY": "test_key"})
    @patch("requests.post")
    def test_speak_http_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "HTTP Error"
        )
        mock_post.return_value = mock_response

        text_queue = queue.Queue()
        self.streamer.speak("Hello world", text_queue)

        self.assertFalse(self.streamer.is_stopped())
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(mock_response.raise_for_status.call_count, 1)


if __name__ == "__main__":
    unittest.main()

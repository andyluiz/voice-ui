import time
import unittest
from unittest.mock import MagicMock, patch

from voice_ui.audio_io.player import Player
from voice_ui.speech_synthesis.google_text_to_speech_streamer import (
    GoogleTextToSpeechAudioStreamer,
)


def player_init(self):
    self._stream = MagicMock()
    self._audio_interface = MagicMock()


class TestGoogleTextToSpeechAudioStreamer(unittest.TestCase):
    @patch("threading.Thread")
    @patch.object(Player, "__init__", new=player_init)
    @patch("google.cloud.texttospeech.TextToSpeechClient")
    def setUp(self, mock_google_tts, mock_thread):
        self.streamer = GoogleTextToSpeechAudioStreamer()

        self.streamer._player = MagicMock()

        mock_google_tts.assert_called_once()
        mock_thread.return_value.start.assert_called_once()

    def tearDown(self):
        del self.streamer

    def test_initialization(self):
        self.assertFalse(self.streamer.is_stopped())
        self.assertFalse(self.streamer.is_speaking())

    def test_stop(self):
        self.streamer.stop()
        self.assertTrue(self.streamer.is_stopped())

    def test_speak_success(self):
        self.streamer.speak("Hello world")

        self.assertFalse(self.streamer.is_stopped())

    def test_speak_exception(self):
        # self.streamer._client.streaming_synthesize.side_effect = [
        #     RuntimeError("Test exception"),
        # ]

        self.streamer.speak("Hello world")

        self.assertFalse(self.streamer.is_stopped())

    def test_available_voices(self):
        expected_voices = [
            {"name": "ALLOY", "gender": "NEUTRAL"},
            {"name": "ECHO", "gender": "MALE"},
            {"name": "FABLE", "gender": "NEUTRAL"},
            {"name": "ONYX", "gender": "MALE"},
            {"name": "NOVA", "gender": "FEMALE"},
            {"name": "SHIMMER", "gender": "FEMALE"},
        ]

        self.streamer._client.list_voices.return_value = MagicMock(
            voices=expected_voices
        )

        voices = self.streamer.available_voices()

        self.streamer._client.list_voices.assert_called_once()
        self.assertEqual(voices, expected_voices)


@unittest.skip("Real-time streaming test")
class TestGoogleTextToSpeechAudioStreamerReal(unittest.TestCase):
    def setUp(self):
        self.streamer = GoogleTextToSpeechAudioStreamer()

    def tearDown(self):
        del self.streamer

    def test_speak(self):
        self.streamer.speak("Hello world.")
        self.streamer.speak("How are you doing? I hope you are doing well.")
        self.streamer.speak("I am doing well, thank you for asking.")

        time.sleep(2)

        self.streamer.speak("Playing before stream timeout.")

        time.sleep(6)

        self.streamer.speak(
            "Playing after stream timeout.",
            voice="en-GB-Journey-D",
            language_code="en-GB",
        )

        # time.sleep(0.5)

        while self.streamer.is_speaking():
            print("Waiting for stream to finish")
            time.sleep(0.5)

        self.assertFalse(self.streamer.is_speaking())

        # time.sleep(10)


if __name__ == "__main__":
    unittest.main()

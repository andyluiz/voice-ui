import unittest
from unittest.mock import MagicMock, patch

from voice_ui.audio_io.audio_data import AudioData
from voice_ui.speech_synthesis.pass_through_text_to_speech_streamer import (
    PassThroughTextToSpeechAudioStreamer,
)


class TestPassThroughStreamer(unittest.TestCase):
    @patch(
        "voice_ui.speech_synthesis.pass_through_text_to_speech_streamer.QueuedAudioPlayer"
    )
    def test_all_methods(self, mock_queued_player_class):
        mock_queued_player = MagicMock()

        streamer = PassThroughTextToSpeechAudioStreamer(
            queued_player=mock_queued_player
        )

        mock_queued_player_class.assert_not_called()
        self.assertIs(streamer._queued_player, mock_queued_player)
        self.assertEqual(streamer.name(), "passthrough")

        # Test speech_queue_size
        mock_queued_player.queue_size.return_value = 5
        self.assertEqual(streamer.speech_queue_size(), 5)
        mock_queued_player.queue_size.assert_called_once()

        # Test stop
        streamer.stop()
        mock_queued_player.stop.assert_called_once()

        # Test resume
        streamer.resume()
        mock_queued_player.resume.assert_called_once()

        # Test is_stopped
        mock_queued_player.is_stopped.return_value = True
        self.assertTrue(streamer.is_stopped())
        mock_queued_player.is_stopped.assert_called_once()

        # Test is_speaking
        mock_queued_player.is_speaking.return_value = False
        self.assertFalse(streamer.is_speaking())
        mock_queued_player.is_speaking.assert_called_once()

        # Test available_voices
        self.assertIsNone(streamer.available_voices())

        # Test terminate
        streamer.terminate()
        mock_queued_player.terminate.assert_called_once()

        # Test __del__
        streamer.__del__()
        self.assertEqual(mock_queued_player.terminate.call_count, 2)  # called again

    @patch(
        "voice_ui.speech_synthesis.pass_through_text_to_speech_streamer.QueuedAudioPlayer"
    )
    def test_speak_raw_bytes_queues_audio(self, mock_queued_player_class):
        mock_queued_player = MagicMock()
        mock_queued_player_class.return_value = mock_queued_player

        streamer = PassThroughTextToSpeechAudioStreamer()

        # speak raw bytes
        streamer.speak(b"abc")

        # verify resume was called
        mock_queued_player.resume.assert_called_once()
        # verify audio was queued
        mock_queued_player.queue_audio.assert_called_once_with(b"abc")
        # verify correct queued_player instance
        self.assertIs(streamer._queued_player, mock_queued_player)

    @patch(
        "voice_ui.speech_synthesis.pass_through_text_to_speech_streamer.QueuedAudioPlayer"
    )
    def test_speak_audio_data_extracts_content_and_queues(
        self, mock_queued_player_class
    ):
        mock_queued_player = MagicMock()
        mock_queued_player_class.return_value = mock_queued_player

        streamer = PassThroughTextToSpeechAudioStreamer()

        # speak AudioData
        ad = AudioData(content=b"def", sample_size=2, rate=16000, channels=1)
        streamer.speak(ad)

        # verify resume was called
        mock_queued_player.resume.assert_called_once()
        # verify audio content (not AudioData object) was queued
        mock_queued_player.queue_audio.assert_called_once_with(b"def")

    @patch(
        "voice_ui.speech_synthesis.pass_through_text_to_speech_streamer.QueuedAudioPlayer"
    )
    def test_multiple_speak_calls_queued_sequentially(self, mock_queued_player_class):
        mock_queued_player = MagicMock()
        mock_queued_player_class.return_value = mock_queued_player

        streamer = PassThroughTextToSpeechAudioStreamer()

        # speak multiple times
        streamer.speak(b"first")
        streamer.speak(b"second")
        streamer.speak(b"third")

        # verify resume was called for each speak
        self.assertEqual(mock_queued_player.resume.call_count, 3)
        # verify all were queued in order
        calls = mock_queued_player.queue_audio.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0][0][0], b"first")
        self.assertEqual(calls[1][0][0], b"second")
        self.assertEqual(calls[2][0][0], b"third")

    @patch(
        "voice_ui.speech_synthesis.pass_through_text_to_speech_streamer.QueuedAudioPlayer"
    )
    def test_speak_with_string_raises_attribute_error(self, mock_queued_player_class):
        mock_queued_player = MagicMock()
        mock_queued_player_class.return_value = mock_queued_player

        streamer = PassThroughTextToSpeechAudioStreamer()

        # speak with string should raise
        with self.assertRaises(AttributeError):
            streamer.speak("this is text")


if __name__ == "__main__":
    unittest.main()

import queue
import unittest
from unittest.mock import MagicMock, call, patch

from voice_ui.audio_io.player import Player
from voice_ui.speech_synthesis.google_text_to_speech_streamer import (
    GoogleTextToSpeechAudioStreamer,
)


def player_init(self):
    self._stream = MagicMock()
    self._audio_interface = MagicMock()


class TestGoogleTextToSpeechAudioStreamer(unittest.TestCase):
    @patch('threading.Thread')
    @patch.object(Player, '__init__', new=player_init)
    @patch('google.cloud.texttospeech.TextToSpeechClient')
    def setUp(self, mock_google_tts, mock_thread):
        self.streamer = GoogleTextToSpeechAudioStreamer()

        self.streamer._player = MagicMock()
        self.streamer._data_queue = MagicMock()

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

    def test_synthesize_request_generator(self):
        test_data = 'test audio data'

        def audio_bytes_queue_side_effect(timeout):
            if self.streamer._data_queue.get.call_count > 1:
                self.streamer._terminated = True
                raise queue.Empty
            return test_data

        self.streamer._data_queue.get.side_effect = audio_bytes_queue_side_effect
        self.streamer._data_queue.get_nowait.side_effect = queue.Empty

        result = list(self.streamer._synthesize_request_generator())

        self.assertEqual(self.streamer._data_queue.get.call_count, 2)
        self.assertEqual(self.streamer._data_queue.task_done.call_count, 1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].input.text, test_data)

    def test_speaker_plays_audio_data(self):
        mock_input_1 = MagicMock()
        mock_input_2 = MagicMock()

        self.streamer._client.streaming_synthesize.return_value = iter(
            [
                mock_input_1,
                mock_input_2,
            ]
        )

        self.streamer._data_queue.get_nowait.side_effect = queue.Empty

        self.streamer._speaker_thread_function()

        self.streamer._player.play_data.assert_has_calls([
            call(mock_input_1.audio_content),
            call(mock_input_2.audio_content),
        ])

        self.assertFalse(self.streamer.is_speaking())

    def test_speaker_handles_exceptions_during_playback(self):
        mock_input_1 = MagicMock()
        mock_input_2 = MagicMock()

        self.streamer._client.streaming_synthesize.return_value = iter(
            [
                mock_input_1,
                mock_input_2,
            ]
        )

        self.streamer._player.play_data.side_effect = Exception("Test exception")

        # On exception, the stream is stopped
        self.streamer._data_queue = MagicMock()
        self.streamer._data_queue.get_nowait.side_effect = queue.Empty

        self.streamer._speaker_thread_function()

        self.streamer._player.play_data.assert_called_once()

        self.streamer._data_queue.get_nowait.assert_called_once()

        self.assertFalse(self.streamer.is_speaking())

    def test_speaker_handles_exceptions_during_init(self):
        self.streamer._client.streaming_synthesize.side_effect = [
            RuntimeError("Test exception"),
        ]

        # On exception, the stream is stopped
        self.streamer._data_queue = MagicMock()
        self.streamer._data_queue.get_nowait.side_effect = queue.Empty

        self.streamer._speaker_thread_function()

        self.streamer._player.play_data.assert_not_called()

        self.streamer._data_queue.get_nowait.assert_called_once()

        self.assertFalse(self.streamer.is_speaking())

    def test_speak_success(self):
        self.streamer.speak("Hello world")

        self.streamer._data_queue.put.assert_called_once_with('Hello world')

    def test_speak_exception(self):
        # self.streamer._client.streaming_synthesize.side_effect = [
        #     RuntimeError("Test exception"),
        # ]

        self.streamer.speak("Hello world")

        self.assertFalse(self.streamer.is_stopped())

    def test_available_voices(self):
        expected_voices = [
            {'name': 'ALLOY', 'gender': 'NEUTRAL'},
            {'name': 'ECHO', 'gender': 'MALE'},
            {'name': 'FABLE', 'gender': 'NEUTRAL'},
            {'name': 'ONYX', 'gender': 'MALE'},
            {'name': 'NOVA', 'gender': 'FEMALE'},
            {'name': 'SHIMMER', 'gender': 'FEMALE'},
        ]

        self.streamer._client.list_voices.return_value = expected_voices

        voices = self.streamer.available_voices()

        self.streamer._client.list_voices.assert_called_once()
        self.assertEqual(voices, expected_voices)


if __name__ == '__main__':
    unittest.main()

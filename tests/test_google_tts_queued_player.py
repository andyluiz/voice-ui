import unittest
from unittest.mock import MagicMock, patch

import voice_ui.audio_io.google_tts_queued_player as google_tts_mod
import voice_ui.audio_io.queued_player as queued_player_mod


class DummyThread:
    def __init__(self, *args, **kwargs):
        self._alive = False

    def start(self):
        # Do not start any background activity during tests
        self._alive = False

    def is_alive(self):
        return self._alive


class TestGoogleTTSQueuedPlayer(unittest.TestCase):
    def setUp(self):
        # Prevent the background thread from starting
        patcher = patch.object(queued_player_mod.threading, "Thread", new=DummyThread)
        self.addCleanup(patcher.stop)
        patcher.start()

        # Create a fake player and client
        self.player = MagicMock()
        self.client = MagicMock()

        # Instance under test
        self.player_instance = google_tts_mod.GoogleTTSQueuedPlayer(
            client=self.client, player=self.player
        )

    def tearDown(self):
        try:
            self.player_instance.terminate()
        except Exception:
            pass

    def test_queue_text_trims_and_puts_into_queue(self):
        self.player_instance.queue_text("  hello  ", voice="V", language_code="en-GB")
        item = self.player_instance._data_queue.get_nowait()
        self.assertEqual(item[0], "hello")
        self.assertEqual(item[1], "V")
        self.assertIsInstance(item[2], dict)

    def test_process_queue_item_plays_audio_and_resets_speaking(self):
        class Resp:
            def __init__(self, audio_content):
                self.audio_content = audio_content

        self.client.streaming_synthesize.return_value = iter(
            [Resp(b"abc"), Resp(b"def")]
        )

        self.player_instance._process_queue_item(
            ("hi", None, {"language_code": "en-US"})
        )

        self.assertTrue(self.player.play_data.called)
        self.assertFalse(self.player_instance._speaking)

    def test_process_queue_item_handles_google_api_error(self):
        class DummyGoogleAPIError(Exception):
            pass

        with patch.object(google_tts_mod, "exceptions") as exc_mod:
            exc_mod.GoogleAPIError = DummyGoogleAPIError
            self.client.streaming_synthesize.side_effect = DummyGoogleAPIError("boom")

            self.player_instance._process_queue_item(("hi", None, {}))
            self.assertFalse(self.player_instance._speaking)

    def test_process_queue_item_handles_generic_exception(self):
        self.client.streaming_synthesize.side_effect = RuntimeError("boom")
        self.player_instance._process_queue_item(("hi", None, {}))
        self.assertFalse(self.player_instance._speaking)

    def test_synthesize_request_generator_yields_additional_requests(self):
        self.player_instance._input_timeout = 0.01
        self.player_instance._data_queue.put(("more", None, {}))

        gen = self.player_instance._synthesize_request_generator("start")
        first = next(gen)
        self.assertIsNotNone(first)
        second = next(gen)
        self.assertIsNotNone(second)
        self.player_instance._terminated = True

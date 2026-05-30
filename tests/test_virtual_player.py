"""Unit tests for VirtualPlayer."""

import time
import unittest

from voice_ui.audio_io.audio_sink import AudioSink
from voice_ui.audio_io.virtual_player import VirtualPlayer


class TestVirtualPlayer(unittest.TestCase):

    def test_is_audio_sink(self):
        player = VirtualPlayer()
        self.assertIsInstance(player, AudioSink)

    def test_audio_properties(self):
        player = VirtualPlayer(sample_rate=24000, channels=2)
        self.assertEqual(player.rate, 24000)
        self.assertEqual(player.channels, 2)
        self.assertEqual(player.chunk_size, 320)
        self.assertEqual(player.sample_size, 2)

    def test_default_properties(self):
        player = VirtualPlayer()
        self.assertEqual(player.rate, 16000)
        self.assertEqual(player.channels, 1)

    def test_not_playing_before_start(self):
        player = VirtualPlayer()
        self.assertFalse(player.is_playing())

    def test_is_playing_after_start(self):
        player = VirtualPlayer()
        player.start()
        self.assertTrue(player.is_playing())
        player.terminate()

    def test_not_playing_after_terminate(self):
        player = VirtualPlayer()
        player.start()
        player.terminate()
        self.assertFalse(player.is_playing())

    def test_idempotent_start(self):
        player = VirtualPlayer()
        player.start()
        player.start()  # second call should be a no-op
        self.assertTrue(player.is_playing())
        player.terminate()

    def test_play_queues_frame(self):
        received = []
        player = VirtualPlayer(on_audio_frame=lambda f: received.append(f))
        player.start()

        frame = b"\x01\x02" * 160
        player.play(frame)
        time.sleep(0.15)

        self.assertIn(frame, received)
        player.terminate()

    def test_play_multiple_frames(self):
        received = []
        player = VirtualPlayer(on_audio_frame=lambda f: received.append(f))
        player.start()

        frames = [b"\x00\x01" * 160, b"\x02\x03" * 160, b"\x04\x05" * 160]
        for f in frames:
            player.play(f)
        time.sleep(0.2)

        self.assertEqual(received, frames)
        player.terminate()

    def test_play_drops_when_queue_full(self):
        player = VirtualPlayer(frame_queue_maxsize=2)
        # Do not start the processor thread, so queue fills up
        player.play(b"a")
        player.play(b"b")
        player.play(b"c")  # should be silently dropped
        self.assertEqual(player._frame_queue.qsize(), 2)

    def test_callback_exception_does_not_crash(self):
        def bad_cb(frame):
            raise RuntimeError("intentional error")

        player = VirtualPlayer(on_audio_frame=bad_cb)
        player.start()
        player.play(b"\x00" * 320)
        time.sleep(0.15)
        # processor thread should still be running
        self.assertTrue(player.is_playing())
        player.terminate()

    def test_terminate_drains_queue(self):
        player = VirtualPlayer()
        # Push frames without starting the processor
        player.play(b"a")
        player.play(b"b")
        player.terminate()
        self.assertEqual(player._frame_queue.qsize(), 0)

    def test_play_without_callback(self):
        """play() with no callback should not raise."""
        player = VirtualPlayer()
        player.start()
        player.play(b"\x00" * 320)
        time.sleep(0.1)
        player.terminate()

    def test_none_sentinel_stops_processor(self):
        """Pushing None into the queue stops the frame processor thread."""
        player = VirtualPlayer()
        player.start()
        # Inject None sentinel directly to trigger the break path
        player._frame_queue.put(None)
        time.sleep(0.15)
        # Thread should have exited; terminate() should complete quickly
        player._running = False
        if player._queue_thread is not None:
            player._queue_thread.join(timeout=1.0)

    def test_terminate_handles_queue_empty_race(self):
        """queue.Empty during drain in terminate() is swallowed."""
        import queue as _queue
        from unittest.mock import MagicMock

        player = VirtualPlayer()
        mock_q = MagicMock()
        mock_q.empty.return_value = False
        mock_q.get_nowait.side_effect = _queue.Empty
        mock_q.qsize.return_value = 0
        player._frame_queue = mock_q
        # Should not raise
        player.terminate()


if __name__ == "__main__":
    unittest.main()

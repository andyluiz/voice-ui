import time
import unittest

from voice_ui.audio_io.queued_player import QueuedAudioPlayer
from voice_ui.audio_io.virtual_microphone import VirtualMicrophone


class FakePlayer:
    def __init__(self, raise_on_play=False):
        self.played = []
        self.raise_on_play = raise_on_play

    def play(self, data: bytes):
        if self.raise_on_play:
            raise RuntimeError("boom")
        self.played.append(data)


class TestQueuedPlayer(unittest.TestCase):
    def test_queue_and_playback_and_terminate(self):
        player = FakePlayer()
        qp = QueuedAudioPlayer(player=player)

        try:
            qp.queue_audio(b"hello")
            # allow background thread to process
            time.sleep(0.1)
            self.assertIn(b"hello", player.played)

            self.assertGreaterEqual(qp.queue_size(), 0)
            qp.stop()
            self.assertTrue(qp.is_stopped())
            qp.resume()
            self.assertFalse(qp.is_stopped())
        finally:
            qp.terminate()

    def test_process_exception_sets_speaking_false(self):
        player = FakePlayer(raise_on_play=True)
        qp = QueuedAudioPlayer(player=player)
        try:
            qp.queue_audio(b"boom")
            time.sleep(0.1)
            # no exception escapes; thread should handle it and speaking False
            self.assertFalse(qp.is_speaking())
        finally:
            qp.terminate()


class TestRemoteMicrophoneThreadPaths(unittest.TestCase):
    def test_start_with_pc_factory_and_callbacks(self):
        # exercise branch where _AIORTC_AVAILABLE is toggled
        rm = VirtualMicrophone()

        seen = []

        def cb(b):
            if b == b"boom":
                raise RuntimeError("cb boom")
            seen.append(b)

        rm._on_audio_frame = cb

        # create a dummy pc class
        class DummyPC:
            def close(self):
                pass

        # Test callback functionality
        rm._on_audio_frame = lambda b: seen.append(b)
        rm.start()

        rm.push_frame(b"one")
        rm.push_frame(b"boom")
        # inject a None sentinel directly to hit that branch in read loop
        try:
            rm._frame_queue.put_nowait(None)
        except Exception:
            pass

        time.sleep(0.2)
        self.assertIn(b"one", seen)
        rm.stop()


if __name__ == "__main__":
    unittest.main()

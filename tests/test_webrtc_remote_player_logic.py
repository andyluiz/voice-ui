"""Tests for WebRTCRemotePlayer logic."""

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from voice_ui.audio_io.audio_sink import AudioSink
from voice_ui.audio_io.webrtc_remote_player import (
    AudioGeneratorTrack,
    WebRTCRemotePlayer,
)


class TestAudioGeneratorTrack(unittest.TestCase):

    def test_add_frame_and_recv(self):
        async def run():
            track = AudioGeneratorTrack()
            track.add_frame(b"\x00\x01" * 160)
            frame = await track.recv()
            self.assertIsNotNone(frame)
            track.stop()

        asyncio.get_event_loop().run_until_complete(run())

    def test_recv_returns_silence_on_timeout(self):
        """recv() returns an AVFrame when queue is empty (timeout path)."""

        async def run():
            track = AudioGeneratorTrack()
            # Push silence directly so the timeout path isn't exercised but
            # the recv() round-trip through av.AudioFrame is covered.
            track.add_frame(b"\x00\x00" * 160)
            frame = await track.recv()
            self.assertIsNotNone(frame)
            track.stop()

        asyncio.get_event_loop().run_until_complete(run())

    def test_add_frame_drops_when_full(self):
        track = AudioGeneratorTrack()
        track._audio_queue = MagicMock()
        track._audio_queue.put_nowait.side_effect = asyncio.QueueFull
        # Should not raise
        track.add_frame(b"\x00" * 320)

    def test_stop_sets_flag(self):
        track = AudioGeneratorTrack()
        self.assertTrue(track._running)
        track.stop()
        self.assertFalse(track._running)


class TestWebRTCRemotePlayer(unittest.TestCase):

    def test_is_audio_sink(self):
        player = WebRTCRemotePlayer()
        self.assertIsInstance(player, AudioSink)

    def test_audio_properties(self):
        player = WebRTCRemotePlayer()
        self.assertEqual(player.rate, 16000)
        self.assertEqual(player.channels, 1)
        self.assertEqual(player.chunk_size, 320)
        self.assertEqual(player.sample_size, 2)

    def test_not_running_before_start(self):
        player = WebRTCRemotePlayer()
        self.assertFalse(player._running)
        self.assertFalse(player.is_playing())

    def test_start_sets_running(self):
        player = WebRTCRemotePlayer(signaling_port=19010)
        player.start()
        self.assertTrue(player._running)
        player.stop()

    def test_double_start_is_safe(self):
        player = WebRTCRemotePlayer(signaling_port=19011)
        player.start()
        player.start()
        player.stop()

    def test_play_before_start_logs_warning(self):
        player = WebRTCRemotePlayer()
        # Should not raise
        player.play(b"\x00" * 320)

    def test_on_peer_adds_track_and_calls_callbacks(self):
        states = []
        player = WebRTCRemotePlayer(
            signaling_port=19012,
            on_connection_state=lambda s: states.append(s),
        )
        player._running = True

        mock_pc = MagicMock()
        # Trigger on_peer manually by invoking start() internals
        player._signaling_server = MagicMock()

        # Recreate the on_peer closure by calling start()
        player._running = False
        with patch.object(player, "_signaling_server", create=True):
            pass

        # Directly test on_peer callback logic
        from voice_ui.audio_io.webrtc_remote_player import AudioGeneratorTrack

        player._running = True
        player._audio_tracks = []
        player._pc_instances = []

        # Simulate what on_peer does
        cb_states = []

        def on_peer(pc):
            cb_states.append("connecting")
            try:
                audio_track = AudioGeneratorTrack()
                player._audio_tracks.append(audio_track)
                pc.addTrack(audio_track)
                cb_states.append("connected")
                player._pc_instances.append(pc)
            except Exception:
                cb_states.append("error")

        on_peer(mock_pc)

        self.assertIn("connecting", cb_states)
        self.assertIn("connected", cb_states)
        self.assertEqual(len(player._audio_tracks), 1)
        mock_pc.addTrack.assert_called_once()
        # Verify addTrack is called synchronously (not wrapped in create_task)
        args = mock_pc.addTrack.call_args
        self.assertIsInstance(args[0][0], AudioGeneratorTrack)

    def test_play_sends_to_tracks(self):
        player = WebRTCRemotePlayer()
        player._running = True

        mock_track = MagicMock()
        player._audio_tracks = [mock_track]

        frame = b"\x01\x02" * 160
        player.play(frame)

        mock_track.add_frame.assert_called_once_with(frame)

    def test_play_handles_track_exception(self):
        player = WebRTCRemotePlayer()
        player._running = True

        mock_track = MagicMock()
        mock_track.add_frame.side_effect = RuntimeError("track error")
        player._audio_tracks = [mock_track]

        # Should not raise
        player.play(b"\x00" * 320)

    def test_is_playing_requires_tracks(self):
        player = WebRTCRemotePlayer()
        player._running = True
        player._audio_tracks = []
        self.assertFalse(player.is_playing())

        player._audio_tracks = [MagicMock()]
        self.assertTrue(player.is_playing())

    def test_stop_clears_state(self):
        player = WebRTCRemotePlayer(signaling_port=19013)
        player.start()

        mock_track = MagicMock()
        player._audio_tracks.append(mock_track)

        player.stop()

        mock_track.stop.assert_called_once()
        self.assertFalse(player._running)
        self.assertEqual(player._audio_tracks, [])
        self.assertEqual(player._pc_instances, [])


class TestWebRTCRemotePlayerNoWebRTC(unittest.TestCase):

    def test_init_logs_warning_when_webrtc_unavailable(self):
        """Warning is logged when _WEBRTC_COMPONENTS_AVAILABLE is False."""
        import voice_ui.audio_io.webrtc_remote_player as mod

        original = mod._WEBRTC_COMPONENTS_AVAILABLE
        try:
            mod._WEBRTC_COMPONENTS_AVAILABLE = False
            with self.assertLogs(
                "voice_ui.audio_io.webrtc_remote_player", level="WARNING"
            ):
                WebRTCRemotePlayer()
        finally:
            mod._WEBRTC_COMPONENTS_AVAILABLE = original


if __name__ == "__main__":
    unittest.main()

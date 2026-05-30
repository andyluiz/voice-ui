"""Unit tests for WebRTCRemotePlayer."""

import unittest
from unittest import mock


class TestWebRTCRemotePlayer(unittest.TestCase):
    """Test WebRTCRemotePlayer class."""

    def test_imports_available(self):
        """Test that WebRTCRemotePlayer can be imported."""
        try:
            from voice_ui.audio_io.webrtc_remote_player import WebRTCRemotePlayer

            self.assertIsNotNone(WebRTCRemotePlayer)
        except ImportError:
            self.skipTest("WebRTC dependencies not available")

    def test_webrtc_remote_player_initialization(self):
        """Test WebRTCRemotePlayer initialization."""
        try:
            from voice_ui.audio_io.webrtc_remote_player import WebRTCRemotePlayer

            # Test default parameters
            player = WebRTCRemotePlayer()
            self.assertEqual(player._signaling_port, 8765)
            self.assertEqual(player._signaling_host, "0.0.0.0")
            self.assertFalse(player._running)

            # Test custom parameters
            callback = mock.Mock()
            player = WebRTCRemotePlayer(
                signaling_port=9000,
                signaling_host="127.0.0.1",
                ice_servers=["stun:stun.l.google.com:19302"],
                on_connection_state=callback,
            )
            self.assertEqual(player._signaling_port, 9000)
            self.assertEqual(player._signaling_host, "127.0.0.1")
            self.assertEqual(player._on_connection_state, callback)
        except ImportError:
            self.skipTest("WebRTC dependencies not available")

    def test_webrtc_remote_player_start_stop(self):
        """Test WebRTCRemotePlayer lifecycle."""
        try:
            from voice_ui.audio_io.webrtc_remote_player import WebRTCRemotePlayer

            player = WebRTCRemotePlayer(signaling_port=9005)
            player.start()
            player.stop()
        except ImportError:
            self.skipTest("WebRTC dependencies not available")

    def test_webrtc_remote_player_is_playing(self):
        """Test is_playing() method."""
        try:
            from voice_ui.audio_io.webrtc_remote_player import WebRTCRemotePlayer

            player = WebRTCRemotePlayer()
            self.assertFalse(player.is_playing())

            player.start()
            # Not playing until we have connected peers
            self.assertFalse(player.is_playing())

            player.stop()
        except ImportError:
            self.skipTest("WebRTC dependencies not available")


if __name__ == "__main__":
    unittest.main()

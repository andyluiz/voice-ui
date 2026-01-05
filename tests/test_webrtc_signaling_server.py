"""Unit tests for WebRTCSignalingServer."""

import unittest
from unittest import mock


class TestWebRTCSignalingServer(unittest.TestCase):
    """Test WebRTCSignalingServer class."""

    def test_imports_available(self):
        """Test that WebRTC signaling server can be imported."""
        try:
            from voice_ui.audio_io.webrtc_signaling_server import (
                _WEBRTC_COMPONENTS_AVAILABLE,
                WebRTCSignalingServer,
            )

            self.assertIsNotNone(WebRTCSignalingServer)
            self.assertIsNotNone(_WEBRTC_COMPONENTS_AVAILABLE)
        except ImportError:
            self.skipTest("WebRTC dependencies not available")

    def test_signaling_server_initialization(self):
        """Test WebRTCSignalingServer initialization with various parameters."""
        try:
            from voice_ui.audio_io.webrtc_signaling_server import WebRTCSignalingServer

            # Test default parameters
            server = WebRTCSignalingServer()
            self.assertEqual(server._port, 8765)
            self.assertEqual(server._host, "0.0.0.0")
            self.assertEqual(server._ice_servers, [])
            self.assertFalse(server._running)

            # Test custom parameters
            ice_servers = ["stun:stun.l.google.com:19302"]
            callback = mock.Mock()
            server = WebRTCSignalingServer(
                port=9000,
                host="127.0.0.1",
                ice_servers=ice_servers,
                on_peer=callback,
            )
            self.assertEqual(server._port, 9000)
            self.assertEqual(server._host, "127.0.0.1")
            self.assertEqual(server._ice_servers, ice_servers)
            self.assertEqual(server._on_peer, callback)
        except ImportError:
            self.skipTest("WebRTC dependencies not available")

    def test_signaling_server_on_peer_property(self):
        """Test WebRTCSignalingServer on_peer property getter/setter."""
        try:
            from voice_ui.audio_io.webrtc_signaling_server import WebRTCSignalingServer

            server = WebRTCSignalingServer()
            self.assertIsNone(server.on_peer)

            callback = mock.Mock()
            server.on_peer = callback
            self.assertEqual(server.on_peer, callback)
        except ImportError:
            self.skipTest("WebRTC dependencies not available")

    def test_signaling_server_start_stop(self):
        """Test WebRTCSignalingServer start/stop lifecycle."""
        try:
            from voice_ui.audio_io.webrtc_signaling_server import WebRTCSignalingServer

            server = WebRTCSignalingServer(port=9001)

            # Server should not be running initially
            self.assertFalse(server._running)

            # Start server
            server.start()

            # Stop server
            server.stop()
            self.assertFalse(server._running)
        except ImportError:
            self.skipTest("WebRTC dependencies not available")

    def test_signaling_server_idempotent_start(self):
        """Test that calling start() multiple times is safe."""
        try:
            from voice_ui.audio_io.webrtc_signaling_server import WebRTCSignalingServer

            server = WebRTCSignalingServer(port=9002)

            # Start twice (should be safe)
            server.start()
            server.start()  # Should return early

            server.stop()
        except ImportError:
            self.skipTest("WebRTC dependencies not available")


if __name__ == "__main__":
    unittest.main()

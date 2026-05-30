"""Unit tests for WebRTCRemoteMicrophone."""

import unittest
from pathlib import Path
from unittest import mock

from voice_ui.audio_io.virtual_microphone import VirtualMicrophone


class TestWebRTCRemoteMicrophone(unittest.TestCase):
    """Test WebRTCRemoteMicrophone class."""

    def test_imports_available(self):
        """Test that WebRTCRemoteMicrophone can be imported."""
        try:
            from voice_ui.audio_io.webrtc_remote_microphone import (
                WebRTCRemoteMicrophone,
            )

            self.assertIsNotNone(WebRTCRemoteMicrophone)
        except ImportError:
            self.skipTest("WebRTC dependencies not available")

    def test_webrtc_remote_microphone_initialization(self):
        """Test WebRTCRemoteMicrophone initialization."""
        try:
            from voice_ui.audio_io.webrtc_remote_microphone import (
                WebRTCRemoteMicrophone,
            )

            # Test default parameters
            remote_mic = WebRTCRemoteMicrophone()
            self.assertEqual(remote_mic._signaling_port, 8765)
            self.assertEqual(remote_mic._signaling_host, "0.0.0.0")
            self.assertFalse(remote_mic._serve_html)
            self.assertIsNone(remote_mic._html_path)

            # Test custom parameters
            callback = mock.Mock()
            remote_mic = WebRTCRemoteMicrophone(
                signaling_port=9000,
                signaling_host="127.0.0.1",
                serve_html=True,
                html_path=Path("sender.html"),
                http_port=9080,
                on_connection_state=callback,
            )
            self.assertEqual(remote_mic._signaling_port, 9000)
            self.assertEqual(remote_mic._signaling_host, "127.0.0.1")
            self.assertTrue(remote_mic._serve_html)
            self.assertEqual(remote_mic._html_path, Path("sender.html"))
            self.assertEqual(remote_mic._http_port, 9080)
            self.assertEqual(remote_mic._on_connection_state, callback)
        except ImportError:
            self.skipTest("WebRTC dependencies not available")

    def test_webrtc_remote_microphone_is_remote_microphone(self):
        """Test that WebRTCRemoteMicrophone is a RemoteMicrophone."""
        try:
            from voice_ui.audio_io.webrtc_remote_microphone import (
                WebRTCRemoteMicrophone,
            )

            remote_mic = WebRTCRemoteMicrophone()
            self.assertIsInstance(remote_mic, VirtualMicrophone)
        except ImportError:
            self.skipTest("WebRTC dependencies not available")

    def test_webrtc_remote_microphone_start_stop(self):
        """Test WebRTCRemoteMicrophone lifecycle."""
        try:
            from voice_ui.audio_io.webrtc_remote_microphone import (
                WebRTCRemoteMicrophone,
            )

            remote_mic = WebRTCRemoteMicrophone(signaling_port=9003)
            remote_mic.start()
            remote_mic.stop()
        except ImportError:
            self.skipTest("WebRTC dependencies not available")

    def test_webrtc_remote_microphone_with_missing_html(self):
        """Test WebRTCRemoteMicrophone with missing HTML file."""
        try:
            from voice_ui.audio_io.webrtc_remote_microphone import (
                WebRTCRemoteMicrophone,
            )

            remote_mic = WebRTCRemoteMicrophone(
                signaling_port=9004,
                serve_html=True,
                html_path=Path("/nonexistent/path/sender.html"),
            )
            remote_mic.start()
            remote_mic.stop()
        except ImportError:
            self.skipTest("WebRTC dependencies not available")


if __name__ == "__main__":
    unittest.main()

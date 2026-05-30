"""Tests for WebRTCSignalingServer signaling message handling."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSignalingMessageHandling(unittest.TestCase):
    """Test _handle_signaling_message with mocked RTCPeerConnection."""

    def setUp(self):
        from voice_ui.audio_io.webrtc_signaling_server import WebRTCSignalingServer

        self.server = WebRTCSignalingServer(port=19001)

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def _make_pc(self):
        pc = MagicMock()
        pc.setRemoteDescription = AsyncMock()
        pc.createAnswer = AsyncMock(return_value=MagicMock(sdp="answer-sdp"))
        pc.setLocalDescription = AsyncMock()
        pc.localDescription = MagicMock(sdp="answer-sdp")
        pc.addIceCandidate = AsyncMock()
        pc.close = AsyncMock()
        return pc

    def _make_ws(self):
        ws = MagicMock()
        ws.send = AsyncMock()
        return ws

    def test_offer_triggers_answer(self):
        pc = self._make_pc()
        ws = self._make_ws()

        message = {"type": "offer", "sdp": "v=0\r\n"}
        self._run(self.server._handle_signaling_message(pc, message, ws))

        pc.setRemoteDescription.assert_awaited_once()
        pc.createAnswer.assert_awaited_once()
        pc.setLocalDescription.assert_awaited_once()
        ws.send.assert_awaited_once()

        sent = json.loads(ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "answer")
        self.assertIn("sdp", sent)

    def test_unknown_message_type_is_ignored(self):
        pc = self._make_pc()
        ws = self._make_ws()

        message = {"type": "unknown_type"}
        # Should not raise
        self._run(self.server._handle_signaling_message(pc, message, ws))

        pc.setRemoteDescription.assert_not_awaited()
        ws.send.assert_not_awaited()

    def test_ice_message_with_no_candidate_is_safe(self):
        pc = self._make_pc()
        ws = self._make_ws()

        # candidate key present but empty
        message = {"type": "ice", "candidate": None}
        self._run(self.server._handle_signaling_message(pc, message, ws))

        pc.addIceCandidate.assert_not_awaited()

    def test_ice_message_with_unparseable_candidate_is_skipped(self):
        pc = self._make_pc()
        ws = self._make_ws()

        message = {
            "type": "ice",
            "candidate": {
                "candidate": "this is not a valid sdp candidate",
                "sdpMid": "audio",
                "sdpMLineIndex": 0,
            },
        }
        # Should not raise; unparseable candidates are skipped
        self._run(self.server._handle_signaling_message(pc, message, ws))

    def test_ice_message_strips_candidate_prefix(self):
        """candidate: strings starting with 'candidate:' should be stripped."""
        pc = self._make_pc()
        ws = self._make_ws()

        # A real candidate SDP line starts with 'candidate:' in the browser
        message = {
            "type": "ice",
            "candidate": {
                "candidate": "candidate: not valid",
                "sdpMid": "audio",
                "sdpMLineIndex": 0,
            },
        }
        # Should not raise even if parsing fails
        self._run(self.server._handle_signaling_message(pc, message, ws))

    def test_on_peer_callback_is_called(self):
        cb = MagicMock()
        self.server.on_peer = cb

        pc = MagicMock()
        cb(pc)
        cb.assert_called_once_with(pc)

    def test_on_peer_property_getter_setter(self):
        cb = MagicMock()
        self.assertIsNone(self.server.on_peer)
        self.server.on_peer = cb
        self.assertEqual(self.server.on_peer, cb)


class TestSignalingServerLifecycle(unittest.TestCase):

    def test_start_sets_running(self):
        from voice_ui.audio_io.webrtc_signaling_server import WebRTCSignalingServer

        server = WebRTCSignalingServer(port=19002)
        self.assertFalse(server._running)
        server.start()
        self.assertTrue(server._running)
        server.stop()
        self.assertFalse(server._running)

    def test_double_start_is_safe(self):
        from voice_ui.audio_io.webrtc_signaling_server import WebRTCSignalingServer

        server = WebRTCSignalingServer(port=19003)
        server.start()
        server.start()  # no-op
        server.stop()

    def test_stop_without_start_is_safe(self):
        from voice_ui.audio_io.webrtc_signaling_server import WebRTCSignalingServer

        server = WebRTCSignalingServer(port=19004)
        server.stop()  # should not raise

    def test_init_logs_warning_when_webrtc_unavailable(self):
        """Warning is logged when _WEBRTC_COMPONENTS_AVAILABLE is False."""
        import voice_ui.audio_io.webrtc_signaling_server as mod
        from voice_ui.audio_io.webrtc_signaling_server import WebRTCSignalingServer

        original = mod._WEBRTC_COMPONENTS_AVAILABLE
        try:
            mod._WEBRTC_COMPONENTS_AVAILABLE = False
            with self.assertLogs(
                "voice_ui.audio_io.webrtc_signaling_server", level="WARNING"
            ):
                WebRTCSignalingServer()
        finally:
            mod._WEBRTC_COMPONENTS_AVAILABLE = original

    def test_start_when_components_unavailable_returns_early(self):
        """start() logs an error and returns when WebRTC components are missing."""
        import voice_ui.audio_io.webrtc_signaling_server as mod
        from voice_ui.audio_io.webrtc_signaling_server import WebRTCSignalingServer

        original = mod._WEBRTC_COMPONENTS_AVAILABLE
        try:
            mod._WEBRTC_COMPONENTS_AVAILABLE = False
            server = WebRTCSignalingServer(port=19005)
            server.start()
            self.assertFalse(server._running)
            self.assertIsNone(server._thread)
        finally:
            mod._WEBRTC_COMPONENTS_AVAILABLE = original

    def test_stop_with_running_true_but_no_thread(self):
        """stop() skips join when _thread is None (covers the 130->132 branch miss)."""
        from voice_ui.audio_io.webrtc_signaling_server import WebRTCSignalingServer

        server = WebRTCSignalingServer(port=19006)
        server._running = True  # pretend server is running
        # _thread remains None (never started)
        server.stop()
        self.assertFalse(server._running)

    def test_run_event_loop_exception_and_finally(self):
        """_run_event_loop() exception handler and finally block are covered."""
        from voice_ui.audio_io.webrtc_signaling_server import WebRTCSignalingServer

        server = WebRTCSignalingServer(port=19007)

        async def raise_immediately():
            raise RuntimeError("serve error for test")

        with patch.object(server, "_serve", raise_immediately):
            server.start()
            if server._thread:
                server._thread.join(timeout=3.0)

        self.assertFalse(server._running)

    def test_serve_websockets_failure_covers_193_194(self):
        """Exception in websockets.serve is caught by _serve's except block."""
        from voice_ui.audio_io.webrtc_signaling_server import WebRTCSignalingServer

        server = WebRTCSignalingServer(port=19008)

        class FailingCtx:
            async def __aenter__(self):
                raise OSError("address in use")

            async def __aexit__(self, *a):
                pass

        with patch(
            "voice_ui.audio_io.webrtc_signaling_server.websockets.serve",
            return_value=FailingCtx(),
        ):
            server.start()
            if server._thread:
                server._thread.join(timeout=3.0)

        self.assertFalse(server._running)


if __name__ == "__main__":
    unittest.main()

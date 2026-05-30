"""Targeted coverage tests for WebRTC components.

These tests drive paths that require careful setup of async handlers and
callbacks defined inside the start() methods.
"""

import asyncio
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_mock_pc():
    """Return a mock RTCPeerConnection whose .on() decorator works correctly."""
    registered = {}

    def mock_on(event_name):
        def decorator(fn):
            registered[event_name] = fn
            return fn

        return decorator

    mock_pc = MagicMock()
    mock_pc.on.side_effect = mock_on
    mock_pc._registered = registered
    return mock_pc


# ---------------------------------------------------------------------------
# WebRTCSignalingServer – ICE candidate parsing path
# ---------------------------------------------------------------------------


class TestSignalingServerICEParsing(unittest.TestCase):
    """Test the ICE candidate parsing branch in _handle_signaling_message."""

    def setUp(self):
        from voice_ui.audio_io.webrtc_signaling_server import WebRTCSignalingServer

        self.server = WebRTCSignalingServer(port=19100)

    def _make_pc(self):
        pc = MagicMock()
        pc.addIceCandidate = AsyncMock()
        return pc

    def _make_ws(self):
        ws = MagicMock()
        ws.send = AsyncMock()
        return ws

    def test_ice_message_with_valid_candidate(self):
        """A valid ICE candidate SDP triggers addIceCandidate."""
        pc = self._make_pc()
        ws = self._make_ws()

        # Valid candidate SDP (without 'candidate:' prefix as aioice expects)
        valid_sdp = "1 1 UDP 2130706431 192.168.1.100 54400 typ host"
        message = {
            "type": "ice",
            "candidate": {
                "candidate": valid_sdp,
                "sdpMid": "audio",
                "sdpMLineIndex": 0,
            },
        }
        _run(self.server._handle_signaling_message(pc, message, ws))
        pc.addIceCandidate.assert_awaited_once()

    def test_ice_message_with_candidate_prefix_stripped(self):
        """candidate: prefix is stripped before parsing."""
        pc = self._make_pc()
        ws = self._make_ws()

        valid_sdp = "candidate:1 1 UDP 2130706431 192.168.1.100 54400 typ host"
        message = {
            "type": "ice",
            "candidate": {
                "candidate": valid_sdp,
                "sdpMid": "audio",
                "sdpMLineIndex": 0,
            },
        }
        _run(self.server._handle_signaling_message(pc, message, ws))
        pc.addIceCandidate.assert_awaited_once()

    def test_ice_message_empty_candidate_string(self):
        """An empty candidate string is silently skipped."""
        pc = self._make_pc()
        ws = self._make_ws()

        message = {
            "type": "ice",
            "candidate": {
                "candidate": "",
                "sdpMid": "audio",
                "sdpMLineIndex": 0,
            },
        }
        _run(self.server._handle_signaling_message(pc, message, ws))
        pc.addIceCandidate.assert_not_awaited()


# ---------------------------------------------------------------------------
# WebRTCRemotePlayer – on_peer callback path
# ---------------------------------------------------------------------------


class TestWebRTCRemotePlayerOnPeer(unittest.TestCase):

    def _start_and_capture(self, player, port):
        """Start player, capture and return the on_peer callback."""
        captured = {}

        class CapturingServer:
            def __init__(self, **kw):
                self._loop = None
                self._running = False
                captured["instance"] = self

            def start(self):
                self._running = True

            def stop(self):
                self._running = False

            @property
            def on_peer(self):
                return captured.get("on_peer")

            @on_peer.setter
            def on_peer(self, cb):
                captured["on_peer"] = cb

        with patch(
            "voice_ui.audio_io.webrtc_remote_player.WebRTCSignalingServer",
            side_effect=lambda **kw: CapturingServer(),
        ):
            player.start()

        return captured.get("on_peer"), captured.get("instance")

    def test_on_peer_registers_track_and_state_changes(self):
        from voice_ui.audio_io.webrtc_remote_player import (
            AudioGeneratorTrack,
            WebRTCRemotePlayer,
        )

        states = []
        player = WebRTCRemotePlayer(
            signaling_port=19101,
            on_connection_state=lambda s: states.append(s),
        )
        on_peer, _ = self._start_and_capture(player, 19101)

        self.assertIsNotNone(on_peer)

        mock_pc = MagicMock()
        on_peer(mock_pc)

        self.assertIn("connecting", states)
        self.assertIn("connected", states)
        self.assertEqual(len(player._audio_tracks), 1)
        self.assertIsInstance(player._audio_tracks[0], AudioGeneratorTrack)
        mock_pc.addTrack.assert_called_once()
        player.stop()

    def test_on_peer_error_triggers_error_state(self):
        from voice_ui.audio_io.webrtc_remote_player import WebRTCRemotePlayer

        states = []
        player = WebRTCRemotePlayer(
            signaling_port=19102,
            on_connection_state=lambda s: states.append(s),
        )
        on_peer, _ = self._start_and_capture(player, 19102)

        mock_pc = MagicMock()
        mock_pc.addTrack.side_effect = RuntimeError("track error")

        on_peer(mock_pc)

        self.assertIn("error", states)
        player.stop()

    def test_stop_with_pc_instances_closes_them(self):
        from voice_ui.audio_io.webrtc_remote_player import WebRTCRemotePlayer

        player = WebRTCRemotePlayer(signaling_port=19103)
        on_peer, server_instance = self._start_and_capture(player, 19103)

        # Simulate a connected peer
        mock_pc = MagicMock()
        mock_pc.addTrack = MagicMock()
        if on_peer:
            on_peer(mock_pc)

        # Give the player a fake event loop so run_coroutine_threadsafe path runs
        mock_loop = MagicMock()
        mock_future = MagicMock()
        mock_future.result = MagicMock(return_value=None)
        mock_loop.is_closed.return_value = False
        with patch("asyncio.run_coroutine_threadsafe", return_value=mock_future):
            if server_instance:
                server_instance._loop = mock_loop
                player._signaling_server = server_instance
            player.stop()

        self.assertFalse(player._running)

    def test_recv_silence_on_timeout(self):
        """AudioGeneratorTrack.recv() returns an AVFrame on timeout."""
        from voice_ui.audio_io.webrtc_remote_player import AudioGeneratorTrack

        async def run():
            track = AudioGeneratorTrack()
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                frame = await track.recv()
            self.assertIsNotNone(frame)
            track.stop()

        _run(run())


# ---------------------------------------------------------------------------
# WebRTCRemoteMicrophone – on_peer / on_track callback paths
# ---------------------------------------------------------------------------


class TestWebRTCRemoteMicrophoneOnTrack(unittest.TestCase):
    """Drive the on_peer / on_track closure in WebRTCRemoteMicrophone.start()."""

    def _start_and_capture_on_peer(self, mic):
        """Patch WebRTCSignalingServer so we can capture the on_peer callback."""
        captured = {}

        class CapturingServer:
            def __init__(self, **kw):
                self._loop = None
                self._running = False
                captured["instance"] = self

            def start(self):
                self._running = True

            def stop(self):
                self._running = False

            @property
            def on_peer(self):
                return captured.get("on_peer")

            @on_peer.setter
            def on_peer(self, cb):
                captured["on_peer"] = cb

        from voice_ui.audio_io.virtual_microphone import VirtualMicrophone

        with patch(
            "voice_ui.audio_io.webrtc_remote_microphone.WebRTCSignalingServer",
            side_effect=lambda **kw: CapturingServer(),
        ), patch.object(VirtualMicrophone, "start"):
            mic.start()

        return captured.get("on_peer")

    def test_on_track_audio_frames_pushed(self):
        """Audio frames received on the track are pushed to VirtualMicrophone."""
        from aiortc.mediastreams import MediaStreamError
        from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone

        mic = WebRTCRemoteMicrophone(signaling_port=19110)
        received = []
        mic.push_frame = lambda f: received.append(f)

        on_peer = self._start_and_capture_on_peer(mic)
        self.assertIsNotNone(on_peer)

        # Build a mock pc with a working @pc.on() decorator
        mock_pc = _make_mock_pc()
        on_peer(mock_pc)

        on_track = mock_pc._registered.get("track")
        self.assertIsNotNone(on_track)

        # Fake track: yields one int16 frame then raises MediaStreamError
        int16_array = np.zeros(320, dtype=np.int16)
        call_count = 0

        class FakeTrack:
            kind = "audio"

            async def recv(self):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    frame = MagicMock()
                    frame.to_ndarray.return_value = int16_array
                    return frame
                raise MediaStreamError()

        _run(on_track(FakeTrack()))

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], int16_array.tobytes())

    def test_on_track_non_audio_track_is_ignored(self):
        """Non-audio tracks are silently ignored."""
        from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone

        mic = WebRTCRemoteMicrophone(signaling_port=19111)
        received = []
        mic.push_frame = lambda f: received.append(f)

        on_peer = self._start_and_capture_on_peer(mic)
        mock_pc = _make_mock_pc()
        on_peer(mock_pc)

        on_track = mock_pc._registered.get("track")

        class FakeVideoTrack:
            kind = "video"

        _run(on_track(FakeVideoTrack()))
        self.assertEqual(received, [])

    def test_on_track_float_frame_converted(self):
        """Float32 audio is converted to int16 before being pushed."""
        from aiortc.mediastreams import MediaStreamError
        from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone

        mic = WebRTCRemoteMicrophone(signaling_port=19112)
        received = []
        mic.push_frame = lambda f: received.append(f)

        on_peer = self._start_and_capture_on_peer(mic)
        mock_pc = _make_mock_pc()
        on_peer(mock_pc)

        on_track = mock_pc._registered.get("track")

        float_array = np.array([0.5, -0.5, 0.0, 1.0], dtype=np.float32)
        call_count = 0

        class FakeTrack:
            kind = "audio"

            async def recv(self):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    frame = MagicMock()
                    frame.to_ndarray.return_value = float_array
                    return frame
                raise MediaStreamError()

        _run(on_track(FakeTrack()))

        self.assertEqual(len(received), 1)
        result = np.frombuffer(received[0], dtype=np.int16)
        self.assertAlmostEqual(int(result[0]), int(0.5 * 32767), delta=1)

    def test_on_track_multichannel_flattened(self):
        """Multi-channel audio is flattened before being pushed."""
        from aiortc.mediastreams import MediaStreamError
        from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone

        mic = WebRTCRemoteMicrophone(signaling_port=19113)
        received = []
        mic.push_frame = lambda f: received.append(f)

        on_peer = self._start_and_capture_on_peer(mic)
        mock_pc = _make_mock_pc()
        on_peer(mock_pc)

        on_track = mock_pc._registered.get("track")

        stereo = np.zeros((2, 160), dtype=np.int16)
        call_count = 0

        class FakeTrack:
            kind = "audio"

            async def recv(self):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    frame = MagicMock()
                    frame.to_ndarray.return_value = stereo
                    return frame
                raise MediaStreamError()

        _run(on_track(FakeTrack()))

        self.assertEqual(len(received), 1)
        result = np.frombuffer(received[0], dtype=np.int16)
        self.assertEqual(result.shape, (320,))

    def test_on_peer_connection_state_callbacks(self):
        """on_connection_state is called with 'connecting' and 'connected'."""
        from aiortc.mediastreams import MediaStreamError
        from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone

        states = []
        mic = WebRTCRemoteMicrophone(
            signaling_port=19114,
            on_connection_state=lambda s: states.append(s),
        )
        mic.push_frame = lambda f: None

        on_peer = self._start_and_capture_on_peer(mic)
        mock_pc = _make_mock_pc()
        on_peer(mock_pc)

        on_track = mock_pc._registered.get("track")

        call_count = 0

        class FakeTrack:
            kind = "audio"

            async def recv(self):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    frame = MagicMock()
                    frame.to_ndarray.return_value = np.zeros(320, dtype=np.int16)
                    return frame
                raise MediaStreamError()

        _run(on_track(FakeTrack()))

        self.assertIn("connecting", states)
        self.assertIn("connected", states)

    def test_on_track_exception_triggers_disconnected(self):
        """An unexpected exception in track processing triggers 'disconnected'."""
        from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone

        states = []
        mic = WebRTCRemoteMicrophone(
            signaling_port=19115,
            on_connection_state=lambda s: states.append(s),
        )

        on_peer = self._start_and_capture_on_peer(mic)
        mock_pc = _make_mock_pc()
        on_peer(mock_pc)

        on_track = mock_pc._registered.get("track")

        class BrokenTrack:
            kind = "audio"

            async def recv(self):
                raise RuntimeError("unexpected error")

        _run(on_track(BrokenTrack()))

        self.assertIn("disconnected", states)


class TestWebRTCRemoteMicrophoneHTTPServer(unittest.TestCase):

    def test_start_http_server_with_real_html_file(self):
        """_start_http_server runs when a real HTML file is provided."""
        from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone

        # Create a temporary HTML file
        fd, html_path = tempfile.mkstemp(suffix=".html")
        try:
            os.write(fd, b"<html><body>test</body></html>")
            os.close(fd)

            mic = WebRTCRemoteMicrophone(
                signaling_port=19120,
                serve_html=True,
                html_path=Path(html_path),
                http_port=19121,
            )
            mic.start()
            time.sleep(0.1)  # let thread start
            mic.stop()
        finally:
            os.unlink(html_path)

    def test_start_http_server_without_html_path(self):
        """serve_html=True with no html_path logs a warning and skips server."""
        from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone

        mic = WebRTCRemoteMicrophone(
            signaling_port=19122,
            serve_html=True,
            html_path=None,
        )
        mic.start()
        mic.stop()
        # No HTTP server should have been created
        self.assertIsNone(mic._http_server)

    def test_stop_with_http_server(self):
        """stop() properly shuts down an active HTTP server."""
        from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone

        fd, html_path = tempfile.mkstemp(suffix=".html")
        try:
            os.write(fd, b"<html/>")
            os.close(fd)

            mic = WebRTCRemoteMicrophone(
                signaling_port=19123,
                serve_html=True,
                html_path=Path(html_path),
                http_port=19124,
            )
            mic.start()
            time.sleep(0.1)
            mic.stop()
            # Should complete without error
        finally:
            os.unlink(html_path)


class TestWebRTCRemoteMicrophoneMoreBranches(unittest.TestCase):
    """Cover additional branch and statement misses in WebRTCRemoteMicrophone."""

    def _start_and_capture_on_peer(self, mic):
        captured = {}

        class CapturingServer:
            def __init__(self, **kw):
                self._loop = None
                self._running = False
                captured["instance"] = self

            def start(self):
                self._running = True

            def stop(self):
                self._running = False

            @property
            def on_peer(self):
                return captured.get("on_peer")

            @on_peer.setter
            def on_peer(self, cb):
                captured["on_peer"] = cb

        from voice_ui.audio_io.virtual_microphone import VirtualMicrophone

        with patch(
            "voice_ui.audio_io.webrtc_remote_microphone.WebRTCSignalingServer",
            side_effect=lambda **kw: CapturingServer(),
        ), patch.object(VirtualMicrophone, "start"):
            mic.start()

        return captured.get("on_peer")

    def test_on_track_second_frame_skips_first_frame_log(self):
        """158->166 branch: second frame skips first_frame logging."""
        from aiortc.mediastreams import MediaStreamError
        from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone

        mic = WebRTCRemoteMicrophone(signaling_port=19130)
        received = []
        mic.push_frame = lambda f: received.append(f)

        on_peer = self._start_and_capture_on_peer(mic)
        mock_pc = _make_mock_pc()
        on_peer(mock_pc)
        on_track = mock_pc._registered.get("track")

        arr = np.zeros(320, dtype=np.int16)
        call_count = 0

        class FakeTrack:
            kind = "audio"

            async def recv(self):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    frame = MagicMock()
                    frame.to_ndarray.return_value = arr
                    return frame
                raise MediaStreamError()

        _run(on_track(FakeTrack()))
        self.assertEqual(len(received), 2)

    def test_on_track_exception_without_connection_state_cb(self):
        """169->exit: exception in track handler with no on_connection_state callback."""
        from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone

        mic = WebRTCRemoteMicrophone(signaling_port=19131)
        on_peer = self._start_and_capture_on_peer(mic)
        mock_pc = _make_mock_pc()
        on_peer(mock_pc)
        on_track = mock_pc._registered.get("track")

        class BrokenTrack:
            kind = "audio"

            async def recv(self):
                raise RuntimeError("unexpected")

        # Should not raise even without on_connection_state
        _run(on_track(BrokenTrack()))

    def test_on_track_integer_non_int16_array_cast(self):
        """Line 152: integer (non-float, non-int16) array is cast to int16."""
        from aiortc.mediastreams import MediaStreamError
        from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone

        mic = WebRTCRemoteMicrophone(signaling_port=19132)
        received = []
        mic.push_frame = lambda f: received.append(f)

        on_peer = self._start_and_capture_on_peer(mic)
        mock_pc = _make_mock_pc()
        on_peer(mock_pc)
        on_track = mock_pc._registered.get("track")

        int32_array = np.array([100, 200, -300], dtype=np.int32)
        call_count = 0

        class FakeTrack:
            kind = "audio"

            async def recv(self):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    frame = MagicMock()
                    frame.to_ndarray.return_value = int32_array
                    return frame
                raise MediaStreamError()

        _run(on_track(FakeTrack()))
        self.assertEqual(len(received), 1)

    def test_stop_http_server_without_thread(self):
        """187->190 branch: stop() when _http_server is set but _http_thread is None."""
        from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone

        mic = WebRTCRemoteMicrophone(signaling_port=19133)
        mock_server = MagicMock()
        mic._http_server = mock_server
        mic._http_thread = None
        # Should not raise
        mic.stop()
        mock_server.shutdown.assert_called_once()

    def test_http_server_start_failure_is_logged(self):
        """Lines 225-226: exception in run_server() is caught and logged."""
        import os
        import tempfile
        from pathlib import Path
        from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone

        fd, html_path = tempfile.mkstemp(suffix=".html")
        os.write(fd, b"<html/>")
        os.close(fd)
        try:
            mic = WebRTCRemoteMicrophone(
                signaling_port=19134,
                serve_html=True,
                html_path=Path(html_path),
                http_port=19135,
            )
            with patch(
                "voice_ui.audio_io.webrtc_remote_microphone.ThreadingHTTPServer",
                side_effect=OSError("port in use"),
            ):
                mic._start_http_server()
                if mic._http_thread:
                    mic._http_thread.join(timeout=2.0)
        finally:
            os.unlink(html_path)


if __name__ == "__main__":
    unittest.main()


class TestWebRTCRemotePlayerPCCloseException(unittest.TestCase):
    """stop() logs and does not raise when pc.close() fails."""

    def _start_and_capture(self, player):
        captured = {}

        class CapturingServer:
            def __init__(self, **kw):
                self._loop = None
                self._running = False
                captured["instance"] = self

            def start(self):
                self._running = True

            def stop(self):
                self._running = False

            @property
            def on_peer(self):
                return captured.get("on_peer")

            @on_peer.setter
            def on_peer(self, cb):
                captured["on_peer"] = cb

        with patch(
            "voice_ui.audio_io.webrtc_remote_player.WebRTCSignalingServer",
            side_effect=lambda **kw: CapturingServer(),
        ):
            player.start()
        return captured.get("on_peer"), captured.get("instance")

    def test_stop_pc_close_exception_is_logged(self):
        from voice_ui.audio_io.webrtc_remote_player import WebRTCRemotePlayer

        player = WebRTCRemotePlayer(signaling_port=19105)
        on_peer, server_instance = self._start_and_capture(player)

        mock_future = MagicMock()
        mock_future.result.side_effect = RuntimeError("close failed")
        mock_loop = MagicMock()

        with patch("asyncio.run_coroutine_threadsafe", return_value=mock_future):
            if server_instance:
                server_instance._loop = mock_loop
                player._signaling_server = server_instance

            player._pc_instances = [MagicMock()]
            player.stop()  # should not raise

        self.assertFalse(player._running)

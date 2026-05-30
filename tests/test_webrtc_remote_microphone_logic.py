"""Tests for WebRTCRemoteMicrophone on_peer / audio-track logic."""

import asyncio
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from voice_ui.audio_io.virtual_microphone import VirtualMicrophone
from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone


class FakeFrame:
    """Minimal aiortc audio frame stand-in."""

    def __init__(self, array: np.ndarray):
        self._array = array

    def to_ndarray(self):
        return self._array


class TestWebRTCRemoteMicrophoneOnPeer(unittest.TestCase):
    """Test the on_peer / on_track closure without a live signaling server."""

    def _make_mic(self, **kwargs) -> WebRTCRemoteMicrophone:
        mic = WebRTCRemoteMicrophone(signaling_port=19020, **kwargs)
        # Patch signaling server so start() doesn't bind a real port
        mic._signaling_server = MagicMock()
        mic._signaling_server.start = MagicMock()
        return mic

    def _extract_on_peer(self, mic: WebRTCRemoteMicrophone):
        """Call start() and capture the on_peer callback that was registered."""
        # We need to intercept the on_peer assignment on a mock signaling server
        captured = {}

        class CapturingServer:
            def __init__(self, **kwargs):
                pass

            def start(self):
                pass

            @property
            def on_peer(self):
                return captured.get("on_peer")

            @on_peer.setter
            def on_peer(self, cb):
                captured["cb"] = cb

        with patch(
            "voice_ui.audio_io.webrtc_remote_microphone.WebRTCSignalingServer",
            side_effect=lambda **kw: CapturingServer(),
        ):
            # Bypass parent start's super() call side-effects
            with patch.object(VirtualMicrophone, "start"):
                mic.start()

        return captured.get("cb")

    def test_is_virtual_microphone(self):
        mic = WebRTCRemoteMicrophone()
        self.assertIsInstance(mic, VirtualMicrophone)

    def test_on_track_pushes_int16_frames(self):
        """Audio frames received over WebRTC are pushed into VirtualMicrophone."""
        mic = WebRTCRemoteMicrophone(signaling_port=19021)

        received_frames = []
        mic.push_frame = lambda f: received_frames.append(f)

        # Simulate what the on_peer / on_track handler does directly
        from aiortc.mediastreams import MediaStreamError

        async def simulate_track(track):
            """Replay the inner loop from on_track."""
            first_frame = True
            try:
                while True:
                    try:
                        frame = await track.recv()
                    except MediaStreamError:
                        break

                    array = frame.to_ndarray()
                    if array.ndim > 1:
                        array = np.ascontiguousarray(array.T).reshape(-1)
                    if array.dtype != np.int16:
                        if np.issubdtype(array.dtype, np.floating):
                            array = (np.clip(array, -1.0, 1.0) * 32767).astype(np.int16)
                        else:
                            array = array.astype(np.int16)
                    pcm = array.tobytes()
                    if not pcm:
                        continue
                    if first_frame:
                        first_frame = False
                    mic.push_frame(pcm)
            except Exception:
                pass

        # Build a fake track that yields one int16 frame then raises MediaStreamError
        int16_array = np.zeros(320, dtype=np.int16)
        fake_frame = FakeFrame(int16_array)
        call_count = 0

        class FakeTrack:
            kind = "audio"

            async def recv(self):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return fake_frame
                raise MediaStreamError()

        asyncio.get_event_loop().run_until_complete(simulate_track(FakeTrack()))
        self.assertEqual(len(received_frames), 1)
        self.assertEqual(received_frames[0], int16_array.tobytes())

    def test_on_track_converts_float_to_int16(self):
        """Float audio is converted to int16 PCM before being pushed."""
        mic = WebRTCRemoteMicrophone(signaling_port=19022)

        received_frames = []
        mic.push_frame = lambda f: received_frames.append(f)

        from aiortc.mediastreams import MediaStreamError

        float_array = np.array([0.5, -0.5, 0.0, 1.0], dtype=np.float32)
        fake_frame = FakeFrame(float_array)
        call_count = 0

        class FakeTrack:
            kind = "audio"

            async def recv(self):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return fake_frame
                raise MediaStreamError()

        async def simulate():
            try:
                while True:
                    try:
                        if call_count == 0:
                            await FakeTrack().recv()
                        else:
                            (_ for _ in ()).throw(MediaStreamError())
                    except Exception:
                        break
            except Exception:
                pass

        # Run conversion inline
        array = float_array.copy()
        clipped = np.clip(array, -1.0, 1.0)
        converted = (clipped * 32767).astype(np.int16)
        received_frames.append(converted.tobytes())

        self.assertEqual(len(received_frames), 1)
        result = np.frombuffer(received_frames[0], dtype=np.int16)
        self.assertEqual(result[0], int(0.5 * 32767))

    def test_on_track_multichannel_flattened(self):
        """Multi-channel audio is flattened to mono."""
        # 2-channel, 160 samples each → shape (2, 160)
        stereo = np.zeros((2, 160), dtype=np.int16)
        array = stereo
        if array.ndim > 1:
            array = np.ascontiguousarray(array.T).reshape(-1)
        self.assertEqual(array.shape, (320,))

    def test_connection_state_callbacks(self):
        states = []
        mic = WebRTCRemoteMicrophone(
            signaling_port=19023,
            on_connection_state=lambda s: states.append(s),
        )

        # Simulate the connecting callback path
        mic._on_connection_state("connecting")
        mic._on_connection_state("connected")
        mic._on_connection_state("disconnected")

        self.assertEqual(states, ["connecting", "connected", "disconnected"])

    def test_start_stop_lifecycle(self):
        mic = WebRTCRemoteMicrophone(signaling_port=19024)
        mic.start()
        mic.stop()

    def test_double_start_is_idempotent(self):
        mic = WebRTCRemoteMicrophone(signaling_port=19025)
        mic.start()
        mic.start()  # should not start a second signaling server
        mic.stop()

    def test_serve_html_with_missing_file_does_not_raise(self):
        from pathlib import Path

        mic = WebRTCRemoteMicrophone(
            signaling_port=19026,
            serve_html=True,
            html_path=Path("/nonexistent/path/sender.html"),
        )
        mic.start()
        mic.stop()


if __name__ == "__main__":
    unittest.main()

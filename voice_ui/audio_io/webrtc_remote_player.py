"""WebRTC remote player for sending audio to WebRTC peers.

This module provides a player implementation that sends audio to WebRTC
peers via a signaling server.
"""

import asyncio
import logging
from typing import Any, Optional

from .player import Player
from .webrtc_signaling_server import WebRTCSignalingServer

logger = logging.getLogger(__name__)

try:
    from aiortc import RTCRtpSender
    from aiortc.mediastreams import AudioStreamTrack

    _WEBRTC_COMPONENTS_AVAILABLE = True
except Exception:
    RTCRtpSender = None  # type: ignore
    AudioStreamTrack = None  # type: ignore
    _WEBRTC_COMPONENTS_AVAILABLE = False


class AudioGeneratorTrack(AudioStreamTrack):
    """Audio track that generates frames from a queue or generator.

    This custom track pulls audio from a queue and sends it to remote peers.
    """

    def __init__(self) -> None:
        super().__init__()
        self._audio_queue: asyncio.Queue = asyncio.Queue()
        self._running = True

    def add_frame(self, frame_bytes: bytes) -> None:
        """Add PCM audio frame to the queue for transmission."""
        try:
            # Try non-blocking put first
            self._audio_queue.put_nowait(frame_bytes)
        except asyncio.QueueFull:
            logger.warning("Audio frame queue full; dropping frame")

    async def recv(self):
        """Receive audio frame from queue and convert to AVFrame."""
        import av

        # Get PCM data from queue
        try:
            pcm_data = await asyncio.wait_for(self._audio_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            # Return silence if no data available
            import numpy as np

            pcm_data = b"\x00\x00" * 160  # 160 samples of silence

        # Convert PCM bytes to numpy array
        import numpy as np

        audio_array = np.frombuffer(pcm_data, dtype=np.int16)

        # Create AVFrame
        frame = av.AudioFrame.from_ndarray(audio_array, format="s16", layout="mono")
        frame.sample_rate = 16000

        return frame

    def stop(self) -> None:
        """Stop the track."""
        self._running = False


class WebRTCRemotePlayer(Player):
    """Player that sends audio to WebRTC peers.

    This class combines Player with WebRTCSignalingServer, providing a
    solution for sending audio to WebRTC peers. Audio can be pushed frame
    by frame via the play() method.

    Args:
        signaling_port: Port for WebSocket signaling server (default 8765).
        signaling_host: Host address to bind to (default "0.0.0.0").
        ice_servers: Optional list of STUN/TURN server URLs.
        on_connection_state: Optional callback for connection state changes
            ("connecting", "connected", "disconnected", "error").

    Example:
        from voice_ui.audio_io.webrtc_remote_player import WebRTCRemotePlayer

        # Create player
        player = WebRTCRemotePlayer(signaling_port=8765)
        player.start()

        # Send audio frames to connected peers
        while True:
            audio_frame = get_audio_frame()  # 320 samples of int16 PCM
            player.play(audio_frame)

        player.stop()
    """

    def __init__(
        self,
        signaling_port: int = 8765,
        signaling_host: str = "0.0.0.0",
        ice_servers: Optional[list] = None,
        on_connection_state: Optional[Any] = None,
    ) -> None:
        super().__init__()

        if not _WEBRTC_COMPONENTS_AVAILABLE:
            logger.warning(
                "WebRTC components not available. "
                "Install voice-ui[webrtc] to enable WebRTC audio sending."
            )

        self._signaling_port = signaling_port
        self._signaling_host = signaling_host
        self._ice_servers = ice_servers or []
        self._on_connection_state = on_connection_state

        self._signaling_server: Optional[WebRTCSignalingServer] = None
        self._audio_tracks: list = []
        self._pc_instances: list = []
        self._running = False

    def start(self) -> None:
        """Start the WebRTC signaling server."""
        if self._running:
            return

        self._running = True

        # Create signaling server with audio sending handler
        self._signaling_server = WebRTCSignalingServer(
            port=self._signaling_port,
            host=self._signaling_host,
            ice_servers=self._ice_servers,
        )

        def on_peer(pc: Any) -> None:
            """Handle new peer connection - set up audio sending."""
            if self._on_connection_state:
                self._on_connection_state("connecting")

            try:
                # Create audio track that will be sent to peer
                audio_track = AudioGeneratorTrack()
                self._audio_tracks.append(audio_track)

                # Add track to peer connection
                asyncio.create_task(pc.addTrack(audio_track, "audio"))

                logger.info("Audio track added for remote peer")

                if self._on_connection_state:
                    self._on_connection_state("connected")

                self._pc_instances.append(pc)
            except Exception as e:
                logger.exception(f"Error setting up audio sending: {e}")
                if self._on_connection_state:
                    self._on_connection_state("error")

        self._signaling_server.on_peer = on_peer
        self._signaling_server.start()

        logger.info(
            f"WebRTCRemotePlayer started. Signaling at "
            f"ws://{self._signaling_host}:{self._signaling_port}"
        )

    def stop(self) -> None:
        """Stop the WebRTC signaling server and close all connections."""
        self._running = False

        for track in self._audio_tracks:
            track.stop()

        for pc in self._pc_instances:
            try:
                pc.close()
            except Exception as e:
                logger.warning(f"Error closing peer connection: {e}")

        if self._signaling_server is not None:
            self._signaling_server.stop()

        self._audio_tracks.clear()
        self._pc_instances.clear()

        logger.info("WebRTCRemotePlayer stopped")

    def play(self, audio_data: bytes) -> None:
        """Send audio data to all connected peers.

        Args:
            audio_data: PCM audio bytes (16-bit signed, 16kHz, mono).
                        Typically 320 samples = 640 bytes.
        """
        if not self._running:
            logger.warning("Player not running; ignoring audio data")
            return

        # Push to all connected audio tracks
        for track in self._audio_tracks:
            try:
                track.add_frame(audio_data)
            except Exception as e:
                logger.exception(f"Error sending audio to track: {e}")

    def is_playing(self) -> bool:
        """Check if player is running and has connected peers."""
        return self._running and len(self._audio_tracks) > 0

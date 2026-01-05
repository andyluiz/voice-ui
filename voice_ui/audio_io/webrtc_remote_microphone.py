"""WebRTC remote microphone for receiving audio from WebRTC peers.

This module provides a microphone implementation that receives audio from
WebRTC peers via a signaling server.
"""

import logging
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, List, Optional

import numpy as np

from .virtual_microphone import VirtualMicrophone
from .webrtc_signaling_server import WebRTCSignalingServer

logger = logging.getLogger(__name__)

try:
    from aiortc.mediastreams import MediaStreamError

    _WEBRTC_COMPONENTS_AVAILABLE = True
except Exception:
    MediaStreamError = Exception  # type: ignore
    _WEBRTC_COMPONENTS_AVAILABLE = False


class WebRTCRemoteMicrophone(VirtualMicrophone):
    """Microphone that receives audio from WebRTC peers.

    This class combines VirtualMicrophone with WebRTCSignalingServer,
    providing a turnkey solution for receiving audio from WebRTC peers.
    Audio is automatically pushed to the internal frame queue as clients
    connect and send audio.

    Args:
        signaling_port: Port for WebSocket signaling server (default 8765).
        signaling_host: Host address to bind to (default "0.0.0.0").
        serve_html: Whether to serve sender.html via HTTP (default False).
        html_path: Path to sender.html file (required if serve_html=True).
        http_port: HTTP server port for serving HTML (default 8000).
        ice_servers: Optional list of STUN/TURN server URLs.
        on_connection_state: Optional callback for connection state changes
            ("connecting", "connected", "disconnected", "error").
        **kwargs: Additional arguments passed to RemoteMicrophone parent class.

    Example:
        from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone

        # Simple: signaling only
        remote_mic = WebRTCRemoteMicrophone(signaling_port=8765)
        remote_mic.start()

        # Advanced: serve HTML + signaling
        remote_mic = WebRTCRemoteMicrophone(
            signaling_port=8765,
            serve_html=True,
            html_path="examples/sender.html",
            http_port=8000,
            ice_servers=["stun:stun.l.google.com:19302"],
        )
        remote_mic.start()

        # Use with VoiceUI
        voice_ui = VoiceUI(
            source_instance=remote_mic,
            speech_callback=handle_speech_event,
        )
        voice_ui.start()
    """

    def __init__(
        self,
        signaling_port: int = 8765,
        signaling_host: str = "0.0.0.0",
        serve_html: bool = False,
        html_path: Optional[Path] = None,
        http_port: int = 8000,
        ice_servers: Optional[List[str]] = None,
        on_connection_state: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        self._signaling_port = signaling_port
        self._signaling_host = signaling_host
        self._serve_html = serve_html
        self._html_path = html_path
        self._http_port = http_port
        self._ice_servers = ice_servers
        self._on_connection_state = on_connection_state

        self._signaling_server: Optional[WebRTCSignalingServer] = None
        self._http_server: Optional[ThreadingHTTPServer] = None
        self._http_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start RemoteMicrophone and WebRTC signaling server."""
        # Start parent RemoteMicrophone
        super().start()

        # Start HTTP server if requested
        if self._serve_html:
            self._start_http_server()

        # Start WebRTC signaling server with audio receiving handler
        self._signaling_server = WebRTCSignalingServer(
            port=self._signaling_port,
            host=self._signaling_host,
            ice_servers=self._ice_servers,
        )

        def on_peer(pc: Any) -> None:
            """Handle new peer connection - set up audio receiving."""
            if self._on_connection_state:
                self._on_connection_state("connecting")

            @pc.on("track")
            async def on_track(track) -> None:  # type: ignore[no-redef]
                """Receive audio track and push frames to RemoteMicrophone."""
                if track.kind != "audio":
                    return

                logger.info(
                    "Remote audio track received; streaming into RemoteMicrophone..."
                )

                first_frame = True
                try:
                    while True:
                        try:
                            frame = await track.recv()
                        except MediaStreamError:
                            break

                        array = frame.to_ndarray()
                        # Handle multi-channel audio
                        if array.ndim > 1:
                            array = np.ascontiguousarray(array.T).reshape(-1)

                        # Convert to int16 PCM if needed
                        if array.dtype != np.int16:
                            if np.issubdtype(array.dtype, np.floating):
                                clipped = np.clip(array, -1.0, 1.0)
                                array = (clipped * 32767).astype(np.int16)
                            else:
                                array = array.astype(np.int16)

                        pcm = array.tobytes()
                        if not pcm:
                            continue

                        if first_frame:
                            first_frame = False
                            logger.debug(
                                f"First remote frame received: {len(pcm)} bytes"
                            )
                            if self._on_connection_state:
                                self._on_connection_state("connected")

                        self.push_frame(pcm)
                except Exception as e:
                    logger.exception(f"Error processing audio track: {e}")
                    if self._on_connection_state:
                        self._on_connection_state("disconnected")

            @pc.on("icecandidate")
            async def on_icecandidate(candidate) -> None:
                """Send local ICE candidates to peer."""
                if candidate is None:
                    return
                # Note: WebSocket sending happens in signaling server

        self._signaling_server.on_peer = on_peer
        self._signaling_server.start()

        logger.info(
            f"WebRTCRemoteMicrophone started. Signaling at "
            f"ws://{self._signaling_host}:{self._signaling_port}"
        )

    def stop(self) -> None:
        """Stop RemoteMicrophone and WebRTC signaling server."""
        if self._signaling_server is not None:
            self._signaling_server.stop()

        if self._http_server is not None:
            self._http_server.shutdown()
            if self._http_thread is not None:
                self._http_thread.join(timeout=1.0)

        super().stop()
        logger.info("WebRTCRemoteMicrophone stopped")

    def _start_http_server(self) -> None:
        """Start HTTP server to serve HTML file."""
        if not self._html_path:
            logger.warning(
                "serve_html=True but html_path not provided; skipping HTTP server"
            )
            return

        html_path = Path(self._html_path)
        if not html_path.exists():
            logger.warning(f"HTML file not found: {html_path}; skipping HTTP server")
            return

        serving_dir = str(html_path.parent)

        def run_server() -> None:
            handler = type(
                "Handler",
                (SimpleHTTPRequestHandler,),
                {"directory": serving_dir},
            )
            try:
                self._http_server = ThreadingHTTPServer(
                    ("127.0.0.1", self._http_port), handler
                )
                logger.info(
                    f"HTTP server started at http://127.0.0.1:{self._http_port} "
                    f"(serving {serving_dir})"
                )
                self._http_server.serve_forever()
            except Exception as e:
                logger.exception(f"HTTP server error: {e}")

        self._http_thread = threading.Thread(target=run_server, daemon=True)
        self._http_thread.start()

"""Generic WebRTC signaling server for bidirectional peer connections.

This module provides a reusable WebSocket signaling server that handles:
- SDP offer/answer exchange
- ICE candidate negotiation
- RTCPeerConnection lifecycle management

The server is transport/direction agnostic - it can be used for sending,
receiving, or bidirectional audio, as well as other media types.

Typical usage:
    signaling_server = WebRTCSignalingServer(port=8765)
    signaling_server.start()

    # In a handler or callback, process returned RTCPeerConnection
    def on_peer_connected(pc):
        # Now attach tracks, set handlers, etc.
        @pc.on("track")
        async def on_track(track):
            ...

    signaling_server.on_peer = on_peer_connected
"""

import asyncio
import json
import logging
import threading
from typing import Any, Callable, List, Optional

logger = logging.getLogger(__name__)

try:
    import websockets
    from aioice.candidate import Candidate as AioiceCandidate
    from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
    from aiortc.rtcconnection import RTCConnection

    _WEBRTC_COMPONENTS_AVAILABLE = True
except Exception:
    websockets = None  # type: ignore
    AioiceCandidate = None  # type: ignore
    RTCIceCandidate = None  # type: ignore
    RTCPeerConnection = None  # type: ignore
    RTCConnection = None  # type: ignore
    _WEBRTC_COMPONENTS_AVAILABLE = False


class WebRTCSignalingServer:
    """Generic WebRTC signaling server for peer connection establishment.

    This server handles WebSocket signaling, SDP offer/answer exchange, and
    ICE candidate negotiation. It returns RTCPeerConnection instances to the
    caller, allowing flexible handling of media (send/receive/both).

    Args:
        port: WebSocket server port (default 8765).
        host: Host address to bind to (default "0.0.0.0").
        ice_servers: Optional list of STUN/TURN server URLs.
        on_peer: Optional callback called with RTCPeerConnection when peer
            connects. Callback should set up track handlers, etc.

    Example:
        server = WebRTCSignalingServer(port=8765)

        def on_peer(pc):
            @pc.on("track")
            async def on_track(track):
                print(f"Track received: {track.kind}")

        server.on_peer = on_peer
        server.start()
    """

    def __init__(
        self,
        port: int = 8765,
        host: str = "0.0.0.0",
        ice_servers: Optional[List[str]] = None,
        on_peer: Optional[Callable[[Any], None]] = None,
    ) -> None:
        if not _WEBRTC_COMPONENTS_AVAILABLE:
            logger.warning(
                "WebRTC components (aiortc, websockets) not available. "
                "Install voice-ui[webrtc] to enable WebRTC."
            )

        self._port = port
        self._host = host
        self._ice_servers = ice_servers or []
        self._on_peer = on_peer

        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def on_peer(self) -> Optional[Callable[[Any], None]]:
        """Get the peer connection handler callback."""
        return self._on_peer

    @on_peer.setter
    def on_peer(self, callback: Optional[Callable[[Any], None]]) -> None:
        """Set the peer connection handler callback.

        Args:
            callback: Function called with RTCPeerConnection when peer connects.
        """
        self._on_peer = callback

    def start(self) -> None:
        """Start the WebSocket signaling server in a background thread."""
        if self._running:
            return

        if not _WEBRTC_COMPONENTS_AVAILABLE:
            logger.error(
                "Cannot start WebRTC signaling server: required components not available"
            )
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._thread.start()
        logger.info(f"WebRTC signaling server starting on {self._host}:{self._port}")

    def stop(self) -> None:
        """Stop the WebSocket signaling server."""
        self._running = False
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        logger.info("WebRTC signaling server stopped")

    def _run_event_loop(self) -> None:
        """Run the asyncio event loop in a background thread."""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._serve())
        except Exception as e:
            logger.exception(f"WebRTC signaling server error: {e}")
        finally:
            self._running = False
            if self._loop is not None:
                self._loop.close()

    async def _serve(self) -> None:
        """Run the WebSocket signaling server."""

        async def handler(websocket) -> None:  # type: ignore[no-untyped-def]
            logger.info("WebSocket client connected; waiting for offer...")
            pc = RTCPeerConnection()

            # Notify caller about new peer
            if self._on_peer:
                try:
                    self._on_peer(pc)
                except Exception as e:
                    logger.exception(f"Error in on_peer handler: {e}")

            try:
                async for raw in websocket:
                    try:
                        message = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.warning("Received invalid JSON message")
                        continue

                    try:
                        await self._handle_signaling_message(pc, message, websocket)
                    except Exception as e:
                        logger.exception(f"Error handling signaling message: {e}")

            except websockets.exceptions.ConnectionClosed:
                logger.info("WebSocket client disconnected")
            except Exception as e:
                logger.exception(f"WebSocket handler error: {e}")
            finally:
                try:
                    await pc.close()
                except Exception:
                    pass
                logger.info("WebRTC peer connection closed")

        try:
            async with websockets.serve(handler, self._host, self._port):
                logger.info(
                    f"WebSocket signaling server listening at "
                    f"ws://{self._host}:{self._port}"
                )
                # Run indefinitely
                await asyncio.Future()
        except Exception as e:
            logger.exception(f"Failed to start signaling server: {e}")

    async def _handle_signaling_message(
        self, pc: Any, message: dict, websocket: Any
    ) -> None:
        """Handle signaling messages from peer."""
        msg_type = message.get("type")

        if msg_type == "offer":
            # Receive offer and send answer
            offer = RTCSessionDescription(
                sdp=message.get("sdp", ""),
                type="offer",
            )
            await pc.setRemoteDescription(offer)
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)

            await websocket.send(
                json.dumps({"type": "answer", "sdp": pc.localDescription.sdp})
            )
            logger.debug("SDP answer sent")

        elif msg_type == "ice":
            # Receive and add ICE candidate
            candidate_data = message.get("candidate")
            if candidate_data:
                sdp = candidate_data.get("candidate", "")
                if sdp.startswith("candidate:"):
                    sdp = sdp.split(" ", 1)[1]

                try:
                    parsed_candidate = AioiceCandidate.from_sdp(sdp)
                except ValueError as e:
                    logger.warning(f"Failed to parse ICE candidate: {e}")
                    return

                ice_candidate = RTCIceCandidate(
                    component=parsed_candidate.component,
                    foundation=parsed_candidate.foundation,
                    ip=parsed_candidate.host,
                    port=parsed_candidate.port,
                    priority=parsed_candidate.priority,
                    protocol=parsed_candidate.transport,
                    type=parsed_candidate.type,
                    relatedAddress=parsed_candidate.related_address,
                    relatedPort=parsed_candidate.related_port,
                    sdpMid=candidate_data.get("sdpMid"),
                    sdpMLineIndex=candidate_data.get("sdpMLineIndex"),
                    tcpType=parsed_candidate.tcptype,
                )
                await pc.addIceCandidate(ice_candidate)
                logger.debug("ICE candidate added")
        else:
            logger.warning(f"Unknown signaling message type: {msg_type}")

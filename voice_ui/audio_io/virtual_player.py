"""VirtualPlayer: programmatic audio frame queuing for playback.

This module provides a queue-based audio player that allows applications to
queue audio frames programmatically. Useful for testing, frame inspection,
or integrating with custom audio sinks.
"""

import logging
import queue
import threading
from typing import Callable, Optional

from .player import Player

logger = logging.getLogger(__name__)


class VirtualPlayer(Player):
    """Queue-based audio player for programmatic frame handling.

    Extends Player with a frame queue that allows applications to queue audio
    programmatically without device playback. Useful for testing, routing audio
    to custom sinks, or building audio pipelines.

    Args:
        on_audio_frame: Optional callback invoked with each frame queued.
        frame_queue_maxsize: Maximum queue size before frames are dropped
            (default 100).

    Example:
        player = VirtualPlayer()
        player.start()

        # Queue audio for playback
        audio_bytes = b'...'  # 320 samples of int16 PCM at 16kHz
        player.play(audio_bytes)

        # Retrieve queued frames
        frame = player._queue.get(timeout=1.0)
        player.terminate()
    """

    def __init__(
        self,
        on_audio_frame: Optional[Callable[[bytes], None]] = None,
        frame_queue_maxsize: int = 100,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> None:
        super().__init__()
        self._on_audio_frame = on_audio_frame
        self._frame_queue: queue.Queue[Optional[bytes]] = queue.Queue(
            maxsize=frame_queue_maxsize
        )
        self._sample_rate = sample_rate
        self._channels = channels
        self._queue_thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        """Start the player and frame processing thread."""
        if self._running:
            return

        self._running = True
        self._queue_thread = threading.Thread(target=self._frame_processor, daemon=True)
        self._queue_thread.start()

    def _frame_processor(self) -> None:
        """Process queued frames and invoke callback."""
        while self._running:
            try:
                frame = self._frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # None signals termination
            if frame is None:
                break

            if self._on_audio_frame:
                try:
                    self._on_audio_frame(frame)
                except Exception:
                    logger.exception("on_audio_frame callback raised exception")

    def play(self, frame_bytes: bytes) -> None:
        """Queue audio frame for playback.

        Args:
            frame_bytes: Raw PCM bytes (int16, 16kHz, mono by default).
        """
        try:
            self._frame_queue.put_nowait(frame_bytes)
        except queue.Full:
            logger.debug("Dropping frame: internal queue full")

    def is_playing(self) -> bool:
        """Check if player is actively running."""
        return self._running

    def terminate(self) -> None:
        """Stop the player and clean up resources."""
        self._running = False

        if self._queue_thread is not None:
            self._queue_thread.join(timeout=0.5)

        # Drain any pending frames
        try:
            while not self._frame_queue.empty():
                self._frame_queue.get_nowait()
        except queue.Empty:
            pass

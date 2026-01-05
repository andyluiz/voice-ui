"""VirtualMicrophone: programmatic audio frame injection.

This module provides a queue-based microphone implementation that allows
applications to inject audio frames programmatically, useful for testing,
WebRTC integration, or any scenario where audio comes from a non-physical source.
"""

import logging
import queue
import threading
from typing import Callable, Optional

from .audio_source import AudioSource

logger = logging.getLogger(__name__)

try:
    import pyaudio

    _PYAUDIO_AVAILABLE = True
    _DEFAULT_SAMPLE_FORMAT = pyaudio.paInt16
except ImportError:
    _PYAUDIO_AVAILABLE = False
    _DEFAULT_SAMPLE_FORMAT = None


class VirtualMicrophone(AudioSource):
    """Queue-based microphone for programmatic audio frame injection.

    This class allows applications to push audio frames (as bytes) into an
    internal queue, which are then consumed like a normal microphone. Useful
    for testing, WebRTC integration, or synthetic audio sources.

    Args:
        on_audio_frame: Optional callback invoked with each frame pushed.
        frame_queue_maxsize: Maximum queue size before frames are dropped
            (default 50).

    Example:
        mic = VirtualMicrophone()
        mic.start()

        # Inject audio frames
        audio_bytes = b'...'  # 320 samples of int16 PCM at 16kHz
        mic.push_frame(audio_bytes)

        # Use like a normal microphone
        frames = mic.read()  # or mic.generator()
        mic.stop()
    """

    # Audio properties (16kHz mono, 320 samples = 20ms)
    _RATE = 16000
    _CHANNELS = 1
    _CHUNK_SIZE = 320  # 20ms at 16kHz
    _SAMPLE_SIZE = 2  # int16

    def __init__(
        self,
        on_audio_frame: Optional[Callable[[bytes], None]] = None,
        frame_queue_maxsize: int = 50,
    ) -> None:
        self._on_audio_frame = on_audio_frame
        self._frame_queue: queue.Queue[Optional[bytes]] = queue.Queue(
            maxsize=frame_queue_maxsize
        )
        self._read_thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        """Start the microphone and frame processing thread."""
        if self._running:
            return

        self._running = True
        self._read_thread = threading.Thread(target=self._frame_processor, daemon=True)
        self._read_thread.start()

    def _frame_processor(self) -> None:
        """Process frames from queue and invoke callback."""
        while self._running:
            try:
                frame = self._frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # None signals stream termination
            if frame is None:
                break

            if self._on_audio_frame:
                try:
                    self._on_audio_frame(frame)
                except Exception:
                    logger.exception("on_audio_frame callback raised exception")

    def push_frame(self, frame_bytes: Optional[bytes]) -> None:
        """Push audio frame into the queue.

        Args:
            frame_bytes: Raw PCM bytes (int16, 16kHz, mono) or None to signal EOF.
        """
        if frame_bytes is None:
            self._running = False

        try:
            self._frame_queue.put_nowait(frame_bytes)
        except queue.Full:
            logger.debug("Dropping frame: internal queue full")

    def read(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """Read a single frame from the queue.

        Args:
            timeout: Timeout in seconds (None = block indefinitely, 0 = non-blocking).

        Returns:
            Frame bytes or None if queue is empty / stream closed.
        """
        try:
            frame = self._frame_queue.get(timeout=timeout)
            return frame if frame is not None else None
        except queue.Empty:
            return None

    def stop(self) -> None:
        """Stop the microphone and clean up resources."""
        self._running = False

        if self._read_thread is not None:
            self._read_thread.join(timeout=0.5)

        # Drain any pending frames
        try:
            while not self._frame_queue.empty():
                self._frame_queue.get_nowait()
        except queue.Empty:
            pass

    def pause(self) -> None:
        """Pause frame processing."""
        self._running = False

    def resume(self) -> None:
        """Resume frame processing (same as start)."""
        self.start()

    def generator(self):
        """Yield audio frames as they arrive in the queue.

        Yields:
            bytes: Raw PCM audio frames (or None if None is pushed to signal EOF).
        """
        self._running = True
        while self._running:
            try:
                frame = self._frame_queue.get(timeout=0.1)
                if frame is None:
                    break
                yield frame
            except queue.Empty:
                continue
            except Exception:
                logger.exception("Error in generator")
                break

    # AudioSourceBase interface
    @property
    def channels(self) -> int:
        return self._CHANNELS

    @property
    def rate(self) -> int:
        return self._RATE

    @property
    def chunk_size(self) -> int:
        return self._CHUNK_SIZE

    @property
    def sample_format(self):
        return _DEFAULT_SAMPLE_FORMAT

    @property
    def sample_size(self) -> int:
        return self._SAMPLE_SIZE

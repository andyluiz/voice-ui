import logging
import queue
import threading
from typing import Any, Optional

from .player import Player

logger = logging.getLogger(__name__)


class QueuedAudioPlayer:
    """
    Manages audio playback from a queue using an internal speaker thread.

    This class encapsulates:
    - Queue management for audio data
    - Internal speaker thread lifecycle
    - Playback control (stop, is_playing, etc.)

    Subclasses can override _process_queue_item() to customize how queue items are handled.
    This separation allows the player to be used independently and makes testing easier.
    """

    def __init__(self, player: Optional[Player] = None):
        """
        Initialize the QueuedAudioPlayer.

        Args:
            player: Optional Player instance. If None, a default Player will be created.
        """
        self._player = player or Player()
        self._stopped = False
        self._speaking = False
        self._lock = threading.Lock()

        self._terminated = False
        self._speaker_thread = threading.Thread(
            target=self._speaker_thread_function,
            daemon=True,
            name='QueuedAudioPlayerThread'
        )

        self._data_queue = queue.Queue()
        self._speaker_thread.start()

    def _speaker_thread_function(self):
        """Internal thread function that consumes items from queue and processes them."""
        self._terminated = False

        while not self._terminated:
            try:
                item = self._data_queue.get(timeout=self._get_queue_timeout())

                if self.is_stopped():
                    continue

                # Delegate item processing to subclass implementation
                self._process_queue_item(item)

            except queue.Empty:
                continue
            except Exception as e:
                self._speaking = False
                logger.error(f'Error while processing queue item: {e}')

    def _get_queue_timeout(self) -> float:
        """Get the timeout for queue.get(). Override for custom timeouts."""
        return 1

    def _process_queue_item(self, item: Any):
        """
        Process a queue item. Override this method to customize behavior.

        Default implementation treats item as raw audio bytes and plays it.

        Args:
            item: Item from the queue to process.
        """
        self._speaking = True
        try:
            self._player.play_data(item)
        finally:
            self._speaking = False

    def queue_audio(self, audio_data: bytes):
        """
        Queue audio data for playback.

        Args:
            audio_data: Raw audio bytes to play.
        """
        logger.debug(f'Queuing {len(audio_data)} bytes of audio')
        self._data_queue.put(audio_data)

    def queue_size(self) -> int:
        """Get the current queue size."""
        return self._data_queue.qsize()

    def stop(self):
        """Stop playback of queued audio."""
        with self._lock:
            self._stopped = True

    def resume(self):
        """Resume playback of queued audio."""
        with self._lock:
            self._stopped = False

    def is_stopped(self) -> bool:
        """Check if playback is stopped."""
        with self._lock:
            return self._stopped

    def is_speaking(self) -> bool:
        """Check if audio is currently being played."""
        return self._speaking

    def terminate(self):
        """Terminate the player and internal speaker thread."""
        self.stop()
        self._terminated = True
        if self._speaker_thread.is_alive():
            self._speaker_thread.join(timeout=5)

    def __del__(self):
        """Ensure proper cleanup when the object is destroyed."""
        self.terminate()

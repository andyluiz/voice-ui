import logging
from typing import Dict, List, Optional, Union

from ..audio_io.audio_data import AudioData
from ..audio_io.player import Player
from ..audio_io.queued_player import QueuedAudioPlayer
from .text_to_speech_streamer import TextToSpeechAudioStreamer

logger = logging.getLogger(__name__)


class PassThroughTextToSpeechAudioStreamer(TextToSpeechAudioStreamer):
    """
    A pass-through TTS streamer that plays pre-recorded audio data.

    This streamer accepts raw audio data and plays it through the audio system.
    It delegates all queue and playback management to QueuedAudioPlayer.
    """

    def __init__(
        self,
        player: Optional[Player] = None,
        queued_player: Optional[QueuedAudioPlayer] = None,
    ):
        """
        Initialize the PassThroughTextToSpeechAudioStreamer.

        Args:
            player: Optional custom Player instance. Used if queued_player is not provided.
            queued_player: Optional custom QueuedAudioPlayer instance. If None, one will be created.
        """
        if queued_player is not None:
            self._queued_player = queued_player
        else:
            self._queued_player = QueuedAudioPlayer(player=player)

    def terminate(self):
        """Terminate the player and internal thread."""
        self._queued_player.terminate()

    @staticmethod
    def name():
        return "passthrough"

    def __del__(self):
        """Ensure proper cleanup when the object is destroyed."""
        self.terminate()

    def speech_queue_size(self) -> int:
        """Get the number of audio chunks in the queue."""
        return self._queued_player.queue_size()

    def stop(self):
        """Stop playback."""
        self._queued_player.stop()

    def resume(self):
        """Resume playback."""
        self._queued_player.resume()

    def is_stopped(self) -> bool:
        """Check if playback is stopped."""
        return self._queued_player.is_stopped()

    def is_speaking(self) -> bool:
        """Check if audio is currently being played."""
        return self._queued_player.is_speaking()

    def available_voices(self) -> List[Dict]:
        """This streamer does not support voice selection."""
        return None

    def speak(
        self,
        text: Union[AudioData, bytes],
        **kwargs,
    ):
        """
        Play audio data.

        Args:
            text: AudioData object or raw audio bytes to play.
            **kwargs: Additional arguments (unused).

        Raises:
            AttributeError: If text is a string (this streamer does not support text).
        """
        if isinstance(text, str):
            raise AttributeError("This stream does not support text")

        # Resume playback if it was stopped
        self.resume()

        if isinstance(text, AudioData):
            audio_data = text.content
        else:
            audio_data = text

        self._queued_player.queue_audio(audio_data)

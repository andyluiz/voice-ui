import logging
from typing import Dict, List, Optional

from google.cloud import texttospeech

from ..audio_io.google_tts_queued_player import GoogleTTSQueuedPlayer
from ..audio_io.player import Player
from .pass_through_text_to_speech_streamer import PassThroughTextToSpeechAudioStreamer

logger = logging.getLogger(__name__)


class GoogleTextToSpeechAudioStreamer(PassThroughTextToSpeechAudioStreamer):
    """
    Google Cloud Text-to-Speech streamer using streaming API.

    Uses GoogleTTSQueuedPlayer to manage TTS synthesis and playback.
    """

    def __init__(self, player: Optional[Player] = None, queued_player: Optional[GoogleTTSQueuedPlayer] = None):
        """Initialize the Google TTS streamer.

        Args:
            player: Optional custom Player instance. Used if queued_player is not provided.
            queued_player: Optional custom GoogleTTSQueuedPlayer instance. If None, one will be created.
        """
        client = texttospeech.TextToSpeechClient()

        # If no custom queued_player provided, create one
        if queued_player is None:
            queued_player = GoogleTTSQueuedPlayer(client=client, player=player, input_timeout=3)

        # Initialize parent with the custom queued player
        # Note: We pass queued_player directly so it uses our GoogleTTSQueuedPlayer
        super().__init__(queued_player=queued_player)

        self._client = client

    @staticmethod
    def name() -> str:
        return "google"

    def available_voices(self, language_code: Optional[str] = None) -> List[Dict]:
        return self._client.list_voices(language_code=language_code)

    def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs,
    ):
        """
        Queue text for TTS synthesis and playback.

        Args:
            text: Text to synthesize.
            voice: Optional voice name. Uses default if not specified.
            **kwargs: Additional options like 'language_code'.
        """
        # Resume playback if it was stopped
        self.resume()

        logger.debug(f'Speaking text: "{text}"')

        # Queue the text using the specialized queued player method
        if hasattr(self._queued_player, 'queue_text'):
            self._queued_player.queue_text(text, voice=voice, **kwargs)
        else:
            # Fallback for base QueuedAudioPlayer (shouldn't happen with GoogleTTSQueuedPlayer)
            self._queued_player.queue_audio((text.strip(), voice, kwargs))

import logging
import os
import wave
from enum import StrEnum, unique
from typing import Dict, List, Optional

import requests

from ..audio_io.player import Player
from ..audio_io.queued_player import QueuedAudioPlayer
from .pass_through_text_to_speech_streamer import PassThroughTextToSpeechAudioStreamer

logger = logging.getLogger(__name__)


class OpenAITextToSpeechAudioStreamer(PassThroughTextToSpeechAudioStreamer):
    @unique
    class Voice(StrEnum):
        ALLOY = "alloy"
        ASH = "ash"
        BALLAD = "ballad"
        CORAL = "coral"
        ECHO = "echo"
        FABLE = "fable"
        ONYX = "onyx"
        NOVA = "nova"
        SAGE = "sage"
        SHIMMER = "shimmer"
        VERSE = "verse"

    def __init__(
        self,
        player: Optional[Player] = None,
        queued_player: Optional[QueuedAudioPlayer] = None,
    ):
        """Initialize the OpenAI TTS streamer.

        Args:
            player: Optional custom Player instance. Used if queued_player is not provided.
            queued_player: Optional custom QueuedAudioPlayer instance. If None, one will be created.
        """
        super().__init__(player=player, queued_player=queued_player)

    @staticmethod
    def name():
        return "openai-tts"

    def available_voices(self) -> List[Dict]:
        return [
            {
                "name": self.Voice.ALLOY,
                "gender": "FEMALE",
            },
            {
                "name": self.Voice.ASH,
                "gender": "MALE",
            },
            {
                "name": self.Voice.BALLAD,
                "gender": "NEUTRAL",
            },
            {
                "name": self.Voice.CORAL,
                "gender": "FEMALE",
            },
            {
                "name": self.Voice.ECHO,
                "gender": "MALE",
            },
            {
                "name": self.Voice.FABLE,
                "gender": "NEUTRAL",
            },
            {
                "name": self.Voice.ONYX,
                "gender": "MALE",
            },
            {
                "name": self.Voice.NOVA,
                "gender": "FEMALE",
            },
            {
                "name": self.Voice.SAGE,
                "gender": "FEMALE",
            },
            {
                "name": self.Voice.SHIMMER,
                "gender": "FEMALE",
            },
            {
                "name": self.Voice.VERSE,
                "gender": "MALE",
            },
        ]

    def speak(
        self,
        text: str,
        voice: Optional[Voice] = None,
        **kwargs,
    ):
        # Resume playback (replaces the old "reset the stopped flag" logic)
        self.resume()

        logger.debug(f'Transcribing text: "{text}"')

        try:
            logger.debug("Making the API request")

            # Send the request to the OpenAI API
            response = requests.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f'Bearer {os.environ["OPENAI_API_KEY"]}',
                    "Content-Type": "application/json; charset=utf-8",
                },
                json={
                    # "model": "tts-1",
                    "model": "gpt-4o-mini-tts",
                    "input": text,
                    "voice": str(voice if voice else self.Voice.SHIMMER),
                    "response_format": "wav",
                    **kwargs,
                },
                stream=True,
            )

            logger.debug("API Response received")

            response.raise_for_status()

            # Stream the content
            logger.debug("Reading chunks from API response")
            num_chunks = 0
            with wave.open(response.raw, "rb") as wf:
                while data := wf.readframes(4800):
                    if self.is_stopped():
                        logger.debug("Stream is stopped. Leaving.")
                        break
                    num_chunks += len(data)
                    self._queued_player.queue_audio(data)
            logger.debug(f"Done reading {num_chunks} chunks from API response")

        except requests.exceptions.HTTPError as e:
            logger.error(f"Error: {e}")
            logger.debug(f"Response headers: {response.headers}")
            logger.debug(f"Response message: {response.json()}")

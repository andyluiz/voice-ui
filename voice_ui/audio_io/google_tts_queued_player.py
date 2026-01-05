import itertools
import logging
import queue
from typing import Any, Optional

from google.api_core import exceptions
from google.cloud import texttospeech

from .audio_sink import AudioSink
from .queued_player import QueuedAudioPlayer

logger = logging.getLogger(__name__)


class GoogleTTSQueuedPlayer(QueuedAudioPlayer):
    """
    Specialized QueuedAudioPlayer for Google Cloud Text-to-Speech streaming.

    Instead of queuing raw audio bytes, this player queues (text, voice, kwargs) tuples
    and synthesizes them on-the-fly using Google's streaming TTS API.

    The template method pattern (_process_queue_item) is used to customize how queue
    items are handled without duplicating threading/queue management code.
    """

    def __init__(
        self,
        client: texttospeech.TextToSpeechClient,
        player: Optional[AudioSink] = None,
        input_timeout: float = 3,
    ):
        """
        Initialize the GoogleTTSQueuedPlayer.

        Args:
            client: Google TextToSpeechClient instance.
            player: Optional AudioSink instance. If None, a default Player will be created.
            input_timeout: Timeout for getting text from queue (Google's streaming has 5 second limit).
        """
        self._client = client
        self._input_timeout = input_timeout
        super().__init__(player=player)

    def _get_queue_timeout(self) -> float:
        """Override timeout to match Google's streaming timeout requirements."""
        return self._input_timeout

    def _process_queue_item(self, item: Any):
        """
        Process a TTS queue item (text, voice, kwargs tuple).

        Args:
            item: Tuple of (text, voice, kwargs) to synthesize and play.
        """
        try:
            (text, voice, kwargs) = item
            logger.debug(f'Synthesizing text: "{text}"')

            self._speaking = True

            # Set the config for the stream. The first request must contain the config,
            # followed by text requests.
            config_request = texttospeech.StreamingSynthesizeRequest(
                streaming_config=texttospeech.StreamingSynthesizeConfig(
                    voice=texttospeech.VoiceSelectionParams(
                        language_code=(kwargs or {}).get("language_code", "en-US"),
                        name=voice if voice else "en-US-Journey-D",
                    )
                )
            )

            streaming_responses = self._client.streaming_synthesize(
                requests=itertools.chain(
                    [config_request],
                    self._synthesize_request_generator(starting_text=text),
                )
            )

            for response in streaming_responses:
                if self.is_stopped():
                    logger.debug("Stream is stopped. Leaving.")
                    break

                if response.audio_content:
                    self._player.play(response.audio_content)

            self._speaking = False

        except exceptions.GoogleAPIError as e:
            logger.error(f"Google API error: {e}")
            self._speaking = False

        except Exception as e:
            logger.error(f"Error while synthesizing/playing audio: {e}")
            self._speaking = False

    def _synthesize_request_generator(self, starting_text: str):
        """Generate streaming synthesis requests from the queue."""
        yield texttospeech.StreamingSynthesizeRequest(
            input=texttospeech.StreamingSynthesisInput(text=starting_text)
        )

        while not self._terminated:
            try:
                # Get more text from the queue while synthesizing
                (text, _, _) = self._data_queue.get(timeout=self._input_timeout)
            except queue.Empty:
                logger.debug("No more text to synthesize")
                return

            logger.debug(f'Streaming additional text: "{text}"')

            yield texttospeech.StreamingSynthesizeRequest(
                input=texttospeech.StreamingSynthesisInput(text=text)
            )

    def queue_text(self, text: str, voice: Optional[str] = None, **kwargs):
        """
        Queue text for TTS synthesis and playback.

        Args:
            text: Text to synthesize.
            voice: Optional voice name (e.g., "en-US-Journey-D"). Uses default if not specified.
            **kwargs: Additional options like 'language_code'.
        """
        logger.debug(f'Queueing text for synthesis: "{text}"')
        self._data_queue.put((text.strip(), voice, kwargs))

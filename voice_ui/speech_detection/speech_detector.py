import logging
import threading
from abc import ABC
from pathlib import Path
from typing import Callable
from uuid import UUID, uuid4

from ..audio_io.audio_data import AudioData
from .speaker_profile_manager import SpeakerProfileManager
from .vad_microphone import MicrophoneVADStream


class SpeechEvent(ABC):
    def __init__(self, **kwargs):
        if self.__class__ == SpeechEvent:
            raise TypeError('SpeechEvent is an abstract class and cannot be instantiated directly')

        self._id = uuid4()

        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)
            else:
                raise AttributeError(f'{self.__class__.__name__} already has attribute {k}')

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def id(self) -> UUID:
        return self._id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return (self.__dict__ == other.__dict__)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.__dict__})'

    def get(self, key: str, default=None):
        return self.__dict__.get(key, default)

    def __getitem__(self, key: str):
        return self.__dict__[key]

    def __iter__(self):
        return iter(self.__dict__.items())

    # def __getattr__(self, key):
    #     if key in self._data:
    #         return self._data[key]
    #     raise AttributeError(f'{self.__class__.__name__} has no attribute {key}')


class MetaDataEvent(SpeechEvent):
    pass


class SpeechStartedEvent(SpeechEvent):
    pass


class PartialSpeechEndedEvent(SpeechEvent):
    pass


class SpeechEndedEvent(SpeechEvent):
    pass


class SpeechDetector:
    def __init__(
        self,
        callback: Callable[[SpeechEvent], None],
        speaker_profiles_dir: Path = None,
        threshold: float = 0.2,
        pre_speech_duration: float = 0.1,
        post_speech_duration: float = 1.5,
        max_speech_duration: float = 10,
        **kwargs,
    ):
        self._mic_stream = MicrophoneVADStream(
            threshold=threshold,
            pre_speech_duration=pre_speech_duration,
            post_speech_duration=post_speech_duration,
            **kwargs,
        )

        self._callback = callback
        self._max_speech_duration = max_speech_duration

        self._speaker_profiles_dir = speaker_profiles_dir
        self._profile_manager = None
        self._thread = None

    def start(self):
        self._profile_manager = SpeakerProfileManager(self._speaker_profiles_dir) if self._speaker_profiles_dir else None

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._mic_stream.pause()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self._profile_manager = None

    def _run(self):
        logging.debug('Speech detector thread started')

        if self._callback is None:
            raise ValueError("Callback is required")

        # Calculate chunk durations
        max_chunks = self._mic_stream.convert_duration_to_chunks(self._max_speech_duration)
        logging.debug(f"Max chunks: {max_chunks}")

        # Initialize counters and flags
        self.collected_chunks = []
        self.speaker_scores = []

        # Resume audio stream
        self._mic_stream.resume()

        # Main loop to process audio chunks
        try:
            speech_detected = False

            for chunk in self._mic_stream.generator():
                if len(chunk) == 0:
                    speech_detected = False
                    self._handle_speech_end()
                    continue

                # Detect start of speech
                if not speech_detected:
                    speech_detected = True
                    self._handle_speech_start()

                if self._profile_manager:
                    audio_frame = self._mic_stream.convert_data(chunk)

                    scores = self._profile_manager.detect_speaker(audio_frame)
                    if scores:
                        self.speaker_scores.append(scores)
                        logging.debug(f"Speaker ID: {self._profile_manager.get_speaker_name(scores)}")

                # Collect chunks during speech detection
                self.collected_chunks.append(chunk)

                # Handle case where collected chunks exceed max duration
                self._handle_collected_chunks_overflow(max_chunks)

            # Handle case where stream was closed before end of the speech
            if speech_detected:
                self._handle_speech_end()

        finally:
            # Pause audio processing when closed
            self._mic_stream.pause()

            del self.collected_chunks

        logging.debug('Speech detector thread finished')

    def _handle_speech_start(self):
        """
        Handle the start of speech detection.
        """
        logging.debug("Speech start detected")

        self._callback(event=SpeechStartedEvent())

    def _handle_speech_end(self):
        """
        Handle the end of speech detection.
        """
        logging.debug("Speech end detected")

        # Find the speaker
        speaker_info = None
        if self._profile_manager:
            # Calculate the average scores for each speaker
            scores = [sum(score) / len(score) for score in zip(*self.speaker_scores)]

            # Get the speaker with the highest average score
            speaker_info = self._profile_manager.get_speaker_name(scores)

        self._callback(
            event=SpeechEndedEvent(
                audio_data=AudioData(
                    channels=self._mic_stream.channels,
                    sample_size=self._mic_stream.sample_size,
                    rate=self._mic_stream.rate,
                    content=b"".join(self.collected_chunks),
                ),
                metadata={
                    "speaker": speaker_info,
                }
            )
        )
        self.collected_chunks.clear()
        self.speaker_scores.clear()

    def _handle_collected_chunks_overflow(self, max_chunks):
        """
        Handle the case where collected chunks exceed the maximum duration.
        """
        n_collected_chunks = len(self.collected_chunks)
        if n_collected_chunks > int(0.8 * max_chunks) or n_collected_chunks > int(1.2 * max_chunks):
            # Find the speaker
            speaker_info = None
            if self._profile_manager:
                # Calculate the average scores for each speaker
                scores = [sum(score) / len(score) for score in zip(*self.speaker_scores)]

                # Get the speaker with the highest average score
                speaker_info = self._profile_manager.get_speaker_name(scores)

            self._callback(
                event=PartialSpeechEndedEvent(
                    audio_data=AudioData(
                        channels=self._mic_stream.channels,
                        sample_size=self._mic_stream.sample_size,
                        rate=self._mic_stream.rate,
                        content=b"".join(self.collected_chunks),
                    ),
                    metadata={
                        "speaker": speaker_info,
                    }
                )
            )
            self.collected_chunks.clear()
            self.speaker_scores.clear()

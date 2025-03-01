import logging
import os
import threading
from abc import ABC
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from uuid import UUID, uuid4

import pveagle

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
        self._speaker_profiles = []
        self._eagle_recognizer = None
        self._thread = None

    def stop(self):
        self._mic_stream.pause()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            self._thread = None

        if self._eagle_recognizer is not None:
            self._eagle_recognizer.delete()
            self._eagle_recognizer = None

    def start(self):
        self._speaker_profiles = []
        if self._speaker_profiles_dir:
            logging.info(f'Loading speaker profiles from {self._speaker_profiles_dir}')
            self._speaker_profiles = SpeakerProfileManager(self._speaker_profiles_dir).load_profiles()
            logging.info(f'Loaded {len(self._speaker_profiles)} speaker profiles')

        if self._eagle_recognizer is not None:
            self._eagle_recognizer.delete()
            self._eagle_recognizer = None

        if self._speaker_profiles:
            self._eagle_recognizer = pveagle.create_recognizer(
                access_key=os.environ['PORCUPINE_ACCESS_KEY'],
                speaker_profiles=list(map(lambda x: x["profile_data"], self._speaker_profiles))
            )
            assert self._eagle_recognizer.frame_length == self._mic_stream.chunk_size, "Frame length mismatch"

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        logging.debug('Speech detector thread started')

        if self._callback is None:
            raise ValueError("Callback is required")

        # Calculate chunk durations
        max_chunks = self._mic_stream.convert_duration_to_chunks(self._max_speech_duration)
        logging.debug(f"Max chunks: {max_chunks}")

        # Initialize counters and flags
        self.collected_chunks = []
        self.speaker_scores = [0] * len(self._speaker_profiles)

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

                if self.speaker_scores:
                    # Convert raw data chunk to audio frame
                    audio_frame = self._mic_stream.convert_data(chunk)

                    scores = self._detect_speaker(audio_frame)
                    if scores:
                        if len(scores) == len(self.speaker_scores):
                            self.speaker_scores = list(map(lambda x, y: x + y, self.speaker_scores, scores))
                            logging.debug(f"Speaker ID: {self._get_speaker_name(scores)}")
                        else:
                            logging.warning(f"Speaker scores length mismatch: {len(scores)} != {len(self.speaker_scores)}")

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

    def _get_speaker_name(self, scores: List[float]) -> Optional[Tuple[str, int, float]]:
        if not scores:
            return None

        # Find the speaker by returning the index of the with the highest score
        speaker_id, score = max(enumerate(scores), key=lambda x: x[1])
        if score < 0.2:
            return None

        speaker_name = list(map(lambda x: x["name"], self._speaker_profiles))[speaker_id]

        return {
            "name": speaker_name,
            "id": speaker_id,
            "score": score,
        }

    def _detect_speaker(self, audio_frame) -> Optional[Tuple[str, int, float]]:
        if self._eagle_recognizer is None:
            logging.error("Eagle recognizer is not initialized")
            return None

        if self._eagle_recognizer.frame_length != len(audio_frame):
            logging.error(f"Frame length mismatch: {self._eagle_recognizer.frame_length} != {len(audio_frame)}")
            return None

        scores = self._eagle_recognizer.process(audio_frame)
        if not scores:
            logging.debug("No speaker detected")
            return None

        return scores

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
        speaker_sum = sum(self.speaker_scores)
        scores = list(map(lambda x: (x / speaker_sum) if speaker_sum > 0 else 0, self.speaker_scores))
        speaker_info = self._get_speaker_name(scores)

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
        self.speaker_scores = [0] * len(self._speaker_profiles)

    def _handle_collected_chunks_overflow(self, max_chunks):
        """
        Handle the case where collected chunks exceed the maximum duration.
        """
        n_collected_chunks = len(self.collected_chunks)
        if n_collected_chunks > int(0.8 * max_chunks) or n_collected_chunks > int(1.2 * max_chunks):
            speaker_sum = sum(self.speaker_scores)
            scores = list(map(lambda x: (x / speaker_sum) if speaker_sum > 0 else 0, self.speaker_scores))
            speaker_info = self._get_speaker_name(scores)

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
            self.speaker_scores = [0] * len(self._speaker_profiles)

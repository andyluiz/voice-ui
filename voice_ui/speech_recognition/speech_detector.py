import logging
import queue
import threading
from abc import ABC
from collections import deque
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import pveagle

from .audio_data import AudioData
from .speaker_profile_manager import SpeakerProfileManager
from .vad_microphone import MicrophoneVADStream


class SpeechEvent(ABC):
    def __init__(self, **kwargs):
        if self.__class__ == SpeechEvent:
            raise TypeError('SpeechEvent is an abstract class and cannot be instantiated directly')

        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)
            else:
                raise AttributeError(f'{self.__class__.__name__} already has attribute {k}')

    @property
    def name(self) -> str:
        return self.__class__.__name__

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


class SpeechDetector(MicrophoneVADStream):
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
        super().__init__(**kwargs)

        self._thread_args = {
            "callback": callback,
            "threshold": threshold,
            "pre_speech_duration": pre_speech_duration,
            "post_speech_duration": post_speech_duration,
            "max_speech_duration": max_speech_duration,
        }

        self._speaker_profiles_dir = speaker_profiles_dir
        self._speaker_profiles = []
        self._eagle_recognizer = None

    def stop(self):
        self.pause()
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
                access_key=self._pv_access_key,
                speaker_profiles=list(map(lambda x: x["profile_data"], self._speaker_profiles))
            )
            assert self._eagle_recognizer.frame_length == self._cobra.frame_length, "Frame length mismatch"

        self._thread = threading.Thread(
            target=self._run,
            kwargs=self._thread_args,
            daemon=True,
        )
        self._thread.start()

    def _run(
        self,
        callback: Callable[[SpeechEvent], None] = None,
        threshold: float = None,
        pre_speech_duration: float = 0.1,
        post_speech_duration: float = 1.0,
        max_speech_duration: float = 10,
    ):
        if callback is None:
            raise ValueError("Callback is required")

        # Set threshold to a default value if not provided
        if threshold is None:
            threshold = self._threshold

        # Calculate chunk durations
        start_chunks, end_chunks, max_chunks = map(
            self._convert_duration_to_chunks,
            [pre_speech_duration, post_speech_duration, max_speech_duration],
        )

        logging.debug(f"Start chunks: {start_chunks}")
        logging.debug(f"End chunks: {end_chunks}")
        logging.debug(f"Max chunks: {max_chunks}")

        # Initialize counters and flags
        self.threshold_counter = deque(maxlen=start_chunks)
        self.above_threshold_counter = 0
        self.below_threshold_counter = 0
        self.speech_detected = False
        self.collected_chunks = []
        self.speaker_scores = [0] * len(self._speaker_profiles)

        # Resume audio stream
        self.resume()

        # Main loop to process audio chunks
        try:
            while not self._closed:
                try:
                    # Process the next audio chunk
                    self._process_next_chunk(
                        callback,
                        threshold,
                        start_chunks,
                        end_chunks,
                        max_chunks,
                    )
                except queue.Empty:
                    continue
        finally:
            # Pause audio processing when closed
            self.pause()

            del self.above_threshold_counter
            del self.below_threshold_counter
            del self.speech_detected
            del self.collected_chunks

    def _process_next_chunk(
        self,
        callback,
        threshold,
        start_chunks,
        end_chunks,
        max_chunks,
    ):
        """
        Process the next audio chunk from the buffer.
        """
        # Get the next audio chunk from buffer
        chunk = self._get_chunk_from_buffer()
        if chunk is None:
            raise RuntimeError("Chunk is none")

        # Convert raw data chunk to audio frame
        audio_frame = self._convert_data(chunk)

        # Determine the probability of voice in the audio frame
        voice_probability = self._cobra.process(audio_frame)

        self.threshold_counter.append(voice_probability)

        acc_voice_probability = sum(self.threshold_counter) / len(self.threshold_counter)
        # logging.debug(
        #     "Voice Probability: {:.2f}%, threshold: {:.2f}%".format(acc_voice_probability, threshold)
        # )

        if acc_voice_probability > threshold:
            # Increment counter for chunks above threshold
            self.above_threshold_counter += 1
            self.below_threshold_counter = 0
            # logging.debug(
            #     "Voice Probability: {:.2f}%, above_threshold_counter: {}".format(
            #         voice_probability, self.above_threshold_counter
            #     )
            # )
        else:
            # Increment counter for chunks below threshold
            self.below_threshold_counter += 1
            self.above_threshold_counter = 0
            # logging.debug(
            #     "Voice Probability: {:.2f}%, below_threshold_counter: {}".format(
            #         voice_probability, self.below_threshold_counter
            #     )
            # )

        # Detect start of speech
        if not self.speech_detected and self.above_threshold_counter >= start_chunks:
            self.speech_detected = True
            self._handle_speech_start(callback)

        # Detect end of speech
        if self.speech_detected and self.below_threshold_counter >= end_chunks:
            self.speech_detected = False
            self._handle_speech_end(callback)

        # Report metadata
        self._handle_metadata_report(callback, voice_probability)

        if self.speech_detected:
            if self.speaker_scores:
                scores = self._detect_speaker(audio_frame)
                self.speaker_scores = list(map(lambda x, y: x + y, self.speaker_scores, scores))
                logging.debug(f"Speaker ID: {self._get_speaker_name(scores)}")

            # Collect chunks during speech detection
            self.collected_chunks.append(chunk)

            # Handle case where collected chunks exceed max duration
            self._handle_collected_chunks_overflow(callback, max_chunks)

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

        scores = self._eagle_recognizer.process(audio_frame)
        if not scores:
            logging.debug("No speaker detected")
            return None

        return scores

    def _handle_speech_start(self, callback):
        """
        Handle the start of speech detection.
        """
        logging.debug("Speech start detected")

        callback(event=SpeechStartedEvent())

        # Add pre-speech chunks to collected chunks
        self.collected_chunks.extend(self._pre_speech_queue)

    def _handle_speech_end(self, callback):
        """
        Handle the end of speech detection.
        """
        logging.debug("Speech end detected")

        # Find the speaker
        speaker_sum = sum(self.speaker_scores)
        scores = list(map(lambda x: (x / speaker_sum) if speaker_sum > 0 else 0, self.speaker_scores))
        speaker_info = self._get_speaker_name(scores)

        callback(
            event=SpeechEndedEvent(
                audio_data=AudioData(
                    channels=self.channels,
                    sample_size=self.sample_size,
                    rate=self.rate,
                    content=b"".join(self.collected_chunks),
                ),
                metadata={
                    "speaker": speaker_info,
                }
            )
        )
        self.collected_chunks.clear()
        self.speaker_scores = [0] * len(self._speaker_profiles)

    def _handle_metadata_report(self, callback, voice_probability):
        """
        Handle the metadata reporting.
        """
        callback(
            event=MetaDataEvent(
                metadata={
                    "voice_probability": voice_probability,
                    "above_threshold_counter": self.above_threshold_counter,
                    "below_threshold_counter": self.below_threshold_counter,
                },
            )
        )

    def _handle_collected_chunks_overflow(self, callback, max_chunks):
        """
        Handle the case where collected chunks exceed the maximum duration.
        """
        n_collected_chunks = len(self.collected_chunks)
        if (
            n_collected_chunks > int(0.8 * max_chunks)
            and self.below_threshold_counter >= 5  # TODO: Make this configurable
        ) or n_collected_chunks > int(1.2 * max_chunks):
            speaker_sum = sum(self.speaker_scores)
            scores = list(map(lambda x: (x / speaker_sum) if speaker_sum > 0 else 0, self.speaker_scores))
            speaker_info = self._get_speaker_name(scores)

            callback(
                event=PartialSpeechEndedEvent(
                    audio_data=AudioData(
                        channels=self.channels,
                        sample_size=self.sample_size,
                        rate=self.rate,
                        content=b"".join(self.collected_chunks),
                    ),
                    metadata={
                        "speaker": speaker_info,
                    }
                )
            )
            self.collected_chunks.clear()
            self.speaker_scores = [0] * len(self._speaker_profiles)

import logging
import math
import os
import struct
from collections import deque
from typing import List, Optional, Union

import pvcobra

from .vad_i import IVoiceActivityDetector


class PicoVoiceVAD(IVoiceActivityDetector):
    def __init__(self, library_path: Optional[str] = None):
        self._cobra = pvcobra.create(
            access_key=os.environ['PORCUPINE_ACCESS_KEY'],
            library_path=library_path
        )

    def __del__(self):
        if self._cobra is not None:
            self._cobra.delete()
            self._cobra = None

    @property
    def frame_length(self) -> int:
        return self._cobra.frame_length

    @property
    def sample_rate(self) -> int:
        return self._cobra.sample_rate

    @staticmethod
    def _convert_data(byte_data):
        int16_values = struct.unpack(f"{len(byte_data) // 2}h", byte_data)
        int16_list = list(int16_values)
        return int16_list

    def _convert_duration_to_chunks(self, duration: float) -> int:
        return int(math.ceil(duration * self.sample_rate / self.frame_length))

    @staticmethod
    def _create_cache(cache: dict, start_chunks: int):
        if "processed_audio_length_ms" not in cache:
            cache["processed_audio_length_ms"] = 0
        if "threshold_counter" not in cache:
            cache["threshold_counter"] = deque(maxlen=start_chunks)
        if "above_threshold_counter" not in cache:
            cache["above_threshold_counter"] = 0
        if "below_threshold_counter" not in cache:
            cache["below_threshold_counter"] = 0
        if "speech_detected" not in cache:
            cache["speech_detected"] = False

    def process(
        self,
        data: Union[bytes, List],
        cache,
        threshold: float = 0.7,
        pre_speech_duration: float = 0.2,
        post_speech_duration: float = 1.0,
        **kwargs
    ) -> bool:
        if isinstance(data, bytes):
            audio_frame = self._convert_data(data)
        elif isinstance(data, list):
            audio_frame = data
        else:
            raise ValueError(f'Invalid data type: {type(data)}')

        # Calculate chunk durations
        start_chunks, end_chunks = map(
            self._convert_duration_to_chunks,
            [pre_speech_duration, post_speech_duration],
        )

        if cache is None:
            raise ValueError("Cache is None")

        self._create_cache(cache, start_chunks)

        voice_probability = self._cobra.process(audio_frame)

        logging.debug(f'VAD result: {voice_probability}')

        cache["threshold_counter"].append(voice_probability)
        cache["processed_audio_length_ms"] += 1000 * self.frame_length / self.sample_rate

        acc_voice_probability = sum(cache["threshold_counter"]) / len(cache["threshold_counter"])
        # logging.debug(
        #     "Voice Probability: {:.2f}%, threshold: {:.2f}%".format(acc_voice_probability, threshold)
        # )

        if acc_voice_probability > threshold:
            # Increment counter for chunks above threshold
            cache["above_threshold_counter"] += 1
            cache["below_threshold_counter"] = 0
            # logging.debug(
            #     "Voice Probability: {:.2f}%, above_threshold_counter: {}".format(
            #         voice_probability, cache["above_threshold_counter"]
            #     )
            # )
        else:
            # Increment counter for chunks below threshold
            cache["below_threshold_counter"] += 1
            cache["above_threshold_counter"] = 0
            # logging.debug(
            #     "Voice Probability: {:.2f}%, below_threshold_counter: {}".format(
            #         voice_probability, cache["below_threshold_counter"]
            #     )
            # )

        # Detect start of speech
        if not cache["speech_detected"] and cache["above_threshold_counter"] >= start_chunks:
            cache["speech_detected"] = True

        # Detect end of speech
        if cache["speech_detected"] and cache["below_threshold_counter"] >= end_chunks:
            cache["speech_detected"] = False

        return cache["speech_detected"]

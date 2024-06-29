import logging
import math
import os
import queue
import struct
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List

import pvcobra
import pveagle
import pvporcupine

from .microphone import MicrophoneStream


class HotwordDetector():
    def __init__(
        self,
        pv_access_key=None,
        keywords=None,
        sensitivities=None,
        additional_keyword_paths: Dict[str, str] = {},
    ):
        self._additional_keyword_paths = additional_keyword_paths

        if keywords is None:
            keywords = self.available_keywords()

        KEYWORD_PATHS = self.available_keyword_paths()
        selected_keyword_paths = [KEYWORD_PATHS[x] for x in keywords]

        logging.info("Listening for one of the following hotwords: {}".format(', '.join(keywords)))

        # Initialize Porcupine with the specified keyword file
        self._handle = pvporcupine.create(
            access_key=pv_access_key,
            # model_path=os.path.abspath('src/resources/porcupine/porcupine_params_pt.pv'),
            keyword_paths=selected_keyword_paths,
            # keywords=keywords,
            sensitivities=sensitivities,
        )

    def __del__(self):
        self._handle.delete()

    def available_keyword_paths(self):
        keyword_paths = pvporcupine.KEYWORD_PATHS

        if self._additional_keyword_paths:
            for keyword, path in self._additional_keyword_paths.items():
                if not os.path.exists(path):
                    raise ValueError(f'Keyword path {path} does not exist')

                keyword_paths[keyword] = os.path.abspath(path)

        return keyword_paths

    def available_keywords(self):
        return self.available_keyword_paths().keys()

    def process(self, audio_frame):
        if len(audio_frame) != self._handle.frame_length:
            raise ValueError(f'Audio frame length is different than expected: {len(audio_frame)} != {self._handle.frame_length}')

        return self._handle.process(audio_frame)


class MicrophoneVADStream(MicrophoneStream):
    def __init__(
        self,
        pv_access_key=None,
        threshold: float = 0.7,
        pre_speech_audio_length: float = 0.25,  # seconds
    ):
        if pv_access_key is None:
            pv_access_key = os.environ['PORCUPINE_ACCESS_KEY']
        self._pv_access_key = pv_access_key
        self._threshold = threshold
        self._pre_speech_audio_length = pre_speech_audio_length

        self._cobra = pvcobra.create(access_key=pv_access_key)

        super().__init__(chunk=self._cobra.frame_length)

        def clamp(value, min, max):
            if value < min:
                return min
            elif value > max:
                return max
            else:
                return value

        self._pre_speech_audio_chunk_count = clamp(self._convert_duration_to_chunks(self._pre_speech_audio_length), 1, 150)
        logging.debug(f'Pre speech audio chunk count: {self._pre_speech_audio_chunk_count}')
        self._pre_speech_queue = deque(maxlen=self._pre_speech_audio_chunk_count)

    def __del__(self):
        if hasattr(self, '_cobra') and self._cobra is not None:
            self._cobra.delete()

    def __exit__(self, type, value, traceback):
        super().__exit__(type, value, traceback)

        self._cobra.delete()

    @staticmethod
    def _convert_data(byte_data):
        int16_values = struct.unpack(f"{len(byte_data)//2}h", byte_data)
        int16_list = list(int16_values)
        return int16_list

    @staticmethod
    def _timer_expired(start_time, timeout=None):
        if timeout is None:
            return False

        expiration_time = start_time + timedelta(seconds=timeout)
        now = datetime.now()
        if now < expiration_time:
            return False

        return True

    def pause(self):
        super().pause()
        self._pre_speech_queue.clear()

    def _get_chunk_from_buffer(self):
        # Consume one chunk from the buffer
        chunk = self._buff.get(timeout=0.05)
        if chunk is not None:
            self._pre_speech_queue.append(chunk)

        return chunk

    def _convert_duration_to_chunks(self, duration: float) -> int:
        return int(math.ceil(duration * self._rate / self._chunk))

    def detect_speech(
        self,
        threshold: int = None,
        timeout: int = None,
        speaker_profiles: List[pveagle.EagleProfile] = None,
    ):
        if threshold is None:
            threshold = self._threshold

        eagle = None
        if speaker_profiles:
            eagle = pveagle.create_recognizer(access_key=self._pv_access_key, speaker_profiles=speaker_profiles)
            assert eagle.frame_length == self._cobra.frame_length

        above_threshold_counter = 0
        start_time = datetime.now()

        self.resume()
        while not self._closed:
            if self._timer_expired(start_time=start_time, timeout=timeout):
                self.pause()
                raise TimeoutError('Timeout')

            try:
                # Consume one chunk from the buffer
                chunk = self._get_chunk_from_buffer()
                if chunk is None:
                    raise RuntimeError('Chunk is none')
                    break

                audio_frame = self._convert_data(chunk)
                voice_probability = self._cobra.process(audio_frame)

                speaker_scores = []
                if eagle is not None:
                    speaker_scores = eagle.process(audio_frame)

                if voice_probability > threshold:
                    above_threshold_counter += 1
                    # print('\rVoice Probability: {:.2f} %, above_threshold_counter: {}'.format(voice_probability, above_threshold_counter))
                else:
                    above_threshold_counter = 0

                if above_threshold_counter > 4:
                    # Determine speaker
                    if eagle is not None:
                        eagle.delete()

                    # Keep the stream running to collect all the next frames, and return
                    return True, speaker_scores

            except queue.Empty:
                # Queue is empty, this is expected, continue
                continue

        self.pause()
        if eagle is not None:
            eagle.delete()
        return False, -1

    def detect_hot_keyword(
        self,
        additional_keyword_paths: Dict[str, str] = {},
    ):
        hotword_detector = HotwordDetector(
            pv_access_key=self._pv_access_key,
            additional_keyword_paths=additional_keyword_paths
        )

        self.resume()
        while not self._closed:
            try:
                # Consume one chunk from the buffer
                chunk = self._get_chunk_from_buffer()
                if chunk is None:
                    raise RuntimeError('Chunk is none')
                    break

                audio_frame = self._convert_data(chunk)
                keyword_index = hotword_detector.process(audio_frame)

                if keyword_index >= 0:
                    # Keep the stream running to collect all the next frames, and return
                    return True

            except queue.Empty:
                # Queue is empty, this is expected, continue
                continue

        self.pause()
        return False

    def generator(self):
        if len(self._pre_speech_queue) > 0:
            data = b"".join(self._pre_speech_queue)
            yield from self._yield_bytes(data, self._max_bytes_per_yield)

        yield from super().generator()

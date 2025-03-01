import logging
import math
import os
import queue
import struct
from collections import deque
from datetime import datetime, timedelta
from typing import Dict

import pvporcupine

from ..audio_io.microphone import MicrophoneStream
from ..voice_activity_detection.vad_factory import VADFactory
from ..voice_activity_detection.vad_i import IVoiceActivityDetector


class HotwordDetector():
    def __init__(
        self,
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
            access_key=os.environ['PORCUPINE_ACCESS_KEY'],
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
        threshold: float = 0.7,
        pre_speech_duration: float = 0.2,  # seconds
        post_speech_duration: float = 0.5,  # seconds
        vad_engine: str = "SileroVAD",
        detection_timeout: float = None,  # seconds
    ):
        """Initialize the MicrophoneVADStream.

        Args:
            threshold (float, optional): Voice activity detection confidence threshold. Defaults to 0.7.
            pre_speech_duration (float, optional): Length in seconds of audio to keep before speech is detected. Defaults to 0.25.
            vad_engine (str, optional): Voice activity detection engine to use. Possible options are 'PicoVoiceVAD',
                                        'FunASRVAD' and 'SileroVAD'. Defaults to "SileroVAD".
        """
        self._threshold = threshold
        self._pre_speech_duration = pre_speech_duration
        self._post_speech_duration = post_speech_duration
        self._detection_timeout = detection_timeout

        self._vad: IVoiceActivityDetector = VADFactory.create(vad_engine)

        super().__init__(rate=16000, chunk=self._vad.frame_length)

        def clamp(value, min, max):
            if value < min:
                return min
            elif value > max:
                return max
            else:
                return value

        self._pre_speech_audio_chunk_count = clamp(self.convert_duration_to_chunks(self._pre_speech_duration), 1, 150)
        logging.debug(f'Pre speech audio chunk count: {self._pre_speech_audio_chunk_count}')
        self._pre_speech_queue = deque(maxlen=self._pre_speech_audio_chunk_count)

    @staticmethod
    def convert_data(byte_data):
        int16_values = struct.unpack(f"{len(byte_data) // 2}h", byte_data)
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

    def _get_chunk_from_buffer(self) -> bytes:
        # Consume one chunk from the buffer
        chunk = self._buff.get(timeout=0.05)
        if chunk is not None:
            self._pre_speech_queue.append(chunk)

        return chunk

    def convert_duration_to_chunks(self, duration: float) -> int:
        return int(math.ceil(duration * self._rate / self._chunk))

    def detect_hot_keyword(
        self,
        additional_keyword_paths: Dict[str, str] = {},
    ):
        hotword_detector = HotwordDetector(
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

                audio_frame = self.convert_data(chunk)
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
        start_time = datetime.now()
        cache = {}
        speech_in_progress: bool = False

        # Start the stream
        self.resume()

        # Keep running this loop until the stream is closed
        while not self._closed:
            try:
                # Consume one chunk from the buffer
                chunk = self._buff.get(timeout=0.1)
                if chunk is None:
                    raise RuntimeError('Chunk is none')
                    break

                vad_res = self._vad.process(
                    chunk,
                    cache=cache,
                    threshold=self._threshold,
                    pre_speech_duration=self._pre_speech_duration,
                    post_speech_duration=self._post_speech_duration,
                )

                # Check if the speech has started
                if not speech_in_progress and vad_res:
                    speech_in_progress = True

                    chunk = b"".join(self._pre_speech_queue) + chunk
                    self._pre_speech_queue.clear()

                # Check if the speech has ended
                if speech_in_progress and not vad_res:
                    speech_in_progress = False

                    # Yield an empty byte string to signal the end of the speech
                    yield b""

                if speech_in_progress:
                    # Reset the start time to prevent timeout
                    start_time = datetime.now()

                    yield chunk
                else:
                    self._pre_speech_queue.append(chunk)

            except queue.Empty:
                # Queue is empty, this is expected, continue
                pass

            if self._timer_expired(start_time=start_time, timeout=self._detection_timeout):
                self.pause()
                raise TimeoutError('Timeout')

        # Stop the stream
        self.pause()

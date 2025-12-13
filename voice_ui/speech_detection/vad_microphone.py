import logging
import math
import queue
import struct
from collections import deque
from datetime import datetime, timedelta
from enum import Enum, auto, unique
from typing import Dict, List, Optional

from ..audio_io.microphone import MicrophoneStream
from ..voice_activity_detection.vad_factory import VADFactory
from ..voice_activity_detection.vad_i import IVoiceActivityDetector
from .hotword_detector import HotwordDetector

logger = logging.getLogger(__name__)


class MicrophoneVADStream(MicrophoneStream):
    @unique
    class DetectionMode(Enum):
        HOTWORD = auto()
        VOICE_ACTIVITY = auto()

    def __init__(
        self,
        threshold: Optional[float] = None,
        pre_speech_duration: Optional[float] = None,  # seconds
        post_speech_duration: Optional[float] = None,  # seconds
        vad_engine: Optional[str] = None,
        detection_timeout: Optional[float] = None,  # seconds
        additional_keyword_paths: Optional[Dict[str, str]] = {},
    ):
        """Initialize the MicrophoneVADStream.

        Args:
            threshold (float, optional): Voice activity detection confidence threshold. Defaults to 0.7.
            pre_speech_duration (float, optional): Length in seconds of audio to keep before speech is detected. Defaults to 0.25.
            vad_engine (str, optional): Voice activity detection engine to use. Possible options are 'PicoVoiceVAD',
                                        'FunASRVAD' and 'SileroVAD'. Defaults to "SileroVAD".
        """
        # Set defaults
        if threshold is None:
            threshold = 0.7
        if pre_speech_duration is None:
            pre_speech_duration = 0.2
        if post_speech_duration is None:
            post_speech_duration = 0.5
        if vad_engine is None:
            vad_engine = "SileroVAD"

        self._threshold = threshold
        self._pre_speech_duration = pre_speech_duration
        self._post_speech_duration = post_speech_duration
        self._detection_timeout = detection_timeout
        self._last_hotword_detected = None

        self._vad: IVoiceActivityDetector = VADFactory.create(vad_engine)
        self._hotword_detector = HotwordDetector(
            additional_keyword_paths=additional_keyword_paths
        )
        self._detection_mode = self.DetectionMode.VOICE_ACTIVITY

        super().__init__(rate=16000, chunk=self._vad.frame_length)

        def clamp(value, min, max):
            if value < min:
                return min
            elif value > max:
                return max
            else:
                return value

        self._pre_speech_audio_chunk_count = clamp(
            self.convert_duration_to_chunks(self._pre_speech_duration), 1, 150
        )
        logger.debug(
            f"Pre speech audio chunk count: {self._pre_speech_audio_chunk_count}"
        )
        self._pre_speech_queue = deque(maxlen=self._pre_speech_audio_chunk_count)

    @property
    def detection_mode(self) -> DetectionMode:
        return self._detection_mode

    def set_detection_mode(self, mode: DetectionMode):
        self._detection_mode = mode

    @property
    def last_hotword_detected(self) -> Optional[str]:
        return self._last_hotword_detected

    @property
    def available_keywords(self) -> List[str]:
        return list(self._hotword_detector.available_keywords())

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
                    raise RuntimeError("Chunk is none")
                    break

                if self.detection_mode == self.DetectionMode.VOICE_ACTIVITY:
                    detection_result = self._vad.process(
                        chunk,
                        cache=cache,
                        threshold=self._threshold,
                        pre_speech_duration=self._pre_speech_duration,
                        post_speech_duration=self._post_speech_duration,
                    )
                elif self.detection_mode == self.DetectionMode.HOTWORD:
                    audio_frame = self.convert_data(chunk)
                    keyword_index = self._hotword_detector.process(audio_frame)

                    detection_result = keyword_index >= 0

                    if detection_result:
                        self._last_hotword_detected = self.available_keywords[
                            keyword_index
                        ]

                        # Switch to voice activity detection if a keyword is detected
                        self.set_detection_mode(self.DetectionMode.VOICE_ACTIVITY)
                    else:
                        self._last_hotword_detected = None
                else:
                    raise ValueError(f"Unknown detection mode: {self.detection_mode}")

                # Check if the speech has started
                if not speech_in_progress and detection_result:
                    speech_in_progress = True

                    chunk = b"".join(self._pre_speech_queue) + chunk
                    self._pre_speech_queue.clear()

                # Check if the speech has ended
                if speech_in_progress and not detection_result:
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

            if self._timer_expired(
                start_time=start_time, timeout=self._detection_timeout
            ):
                self.pause()
                raise TimeoutError("Timeout")

        # Stop the stream
        self.pause()

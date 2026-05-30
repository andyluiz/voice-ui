import logging
import math
import struct
from collections import deque
from datetime import datetime, timedelta
from enum import Enum, auto, unique
from typing import Deque, Dict, Iterator, List, Optional

from ..audio_io.audio_source import AudioSource
from ..audio_io.audio_source_factory import AudioSourceFactory
from ..voice_activity_detection.vad_factory import VADFactory
from ..voice_activity_detection.vad_i import IVoiceActivityDetector
from .hotword_detector import HotwordDetector

logger = logging.getLogger(__name__)


def _clamp(value: int, min_value: int, max_value: int) -> int:
    if value < min_value:
        return min_value
    if value > max_value:
        return max_value
    return value


class VADAudioSource(AudioSource):
    """Audio source wrapper that applies VAD and optional hotword detection.

    This class wraps any `AudioSourceBase` implementation (microphone,
    remote, or custom) and exposes a generator that yields only detected
    speech segments. Utterance boundaries are marked with an empty bytes
    chunk (`b""`).
    """

    @unique
    class DetectionMode(Enum):
        HOTWORD = auto()
        VOICE_ACTIVITY = auto()

    def __init__(
        self,
        threshold: Optional[float] = None,
        pre_speech_duration: Optional[float] = None,
        post_speech_duration: Optional[float] = None,
        vad_engine: Optional[str] = None,
        detection_timeout: Optional[float] = None,
        additional_keyword_paths: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> None:
        # Defaults
        if threshold is None:
            threshold = 0.7
        if pre_speech_duration is None:
            pre_speech_duration = 0.2
        if post_speech_duration is None:
            post_speech_duration = 0.5
        if vad_engine is None:
            vad_engine = "SileroVAD"
        if additional_keyword_paths is None:
            additional_keyword_paths = {}

        self._threshold = threshold
        self._pre_speech_duration = pre_speech_duration
        self._post_speech_duration = post_speech_duration
        self._detection_timeout = detection_timeout
        self._last_hotword_detected: Optional[str] = None

        self._vad: IVoiceActivityDetector = VADFactory.create(vad_engine)
        self._hotword_detector = HotwordDetector(
            additional_keyword_paths=additional_keyword_paths
        )
        self._detection_mode = self.DetectionMode.VOICE_ACTIVITY

        # Underlying audio source selection
        source_instance = kwargs.pop("source_instance", None)
        source_name = kwargs.pop("source_name", None)
        source_kwargs = kwargs.pop("source_kwargs", None) or {}

        if source_instance is not None:
            self._source: AudioSource = source_instance
        else:
            name = source_name if source_name is not None else "microphone"
            self._source = AudioSourceFactory.create(name, **source_kwargs)

        # Cache basic audio parameters from the underlying source
        self._rate = self._source.rate
        self._chunk = self._source.chunk_size
        self._channels = self._source.channels

        pre_speech_chunks = self.convert_duration_to_chunks(self._pre_speech_duration)
        pre_speech_chunks = _clamp(pre_speech_chunks, 1, 150)
        logger.debug("Pre speech audio chunk count: %s", pre_speech_chunks)
        self._pre_speech_queue: Deque[bytes] = deque(maxlen=pre_speech_chunks)

        self._closed = False

    # AudioSourceBase interface -------------------------------------------------
    @property
    def channels(self) -> int:
        return self._channels

    @property
    def rate(self) -> int:
        return self._rate

    @property
    def chunk_size(self) -> int:
        return self._chunk

    @property
    def sample_format(self):
        return self._source.sample_format

    @property
    def sample_size(self) -> int:
        return self._source.sample_size

    def resume(self) -> None:
        self._closed = False
        try:
            self._source.resume()
        except Exception:
            pass

    def pause(self) -> None:
        try:
            self._source.pause()
        except Exception:
            pass
        self._closed = True
        self._pre_speech_queue.clear()

    # VAD/hotword configuration -------------------------------------------------
    @property
    def detection_mode(self) -> "VADAudioSource.DetectionMode":
        return self._detection_mode

    def set_detection_mode(self, mode: "VADAudioSource.DetectionMode") -> None:
        self._detection_mode = mode

    @property
    def last_hotword_detected(self) -> Optional[str]:
        return self._last_hotword_detected

    @property
    def available_keywords(self) -> List[str]:
        return list(self._hotword_detector.available_keywords())

    # Helpers -------------------------------------------------------------------
    @staticmethod
    def convert_data(byte_data: bytes) -> List[int]:
        if len(byte_data) < 2:
            return []
        if len(byte_data) % 2 != 0:
            byte_data = byte_data[:-1]
        int16_values = struct.unpack(f"{len(byte_data) // 2}h", byte_data)
        return list(int16_values)

    @staticmethod
    def _timer_expired(start_time: datetime, timeout: Optional[float] = None) -> bool:
        if timeout is None:
            return False
        expiration_time = start_time + timedelta(seconds=timeout)
        return datetime.now() >= expiration_time

    def convert_duration_to_chunks(self, duration: float) -> int:
        return int(math.ceil(duration * self._rate / self._chunk))

    # Core streaming logic ------------------------------------------------------
    def _process_chunk(
        self,
        chunk: bytes,
        cache: Dict,
        speech_in_progress: bool,
    ) -> (bool, List[bytes]):
        """Apply VAD/hotword logic to a single chunk.

        Returns a tuple of (`speech_in_progress`, `chunks`), where `chunks`
        is a list of non-empty speech chunks and/or a single `b""` marker
        indicating end of an utterance.
        """
        # Default to the last known VAD state for streaming continuity.
        detection_result = cache.get("speech_detected", False)

        if self._detection_mode == self.DetectionMode.VOICE_ACTIVITY:
            # Many VAD engines (including Silero) expect fixed-size frames.
            # When the underlying source yields arbitrary-sized chunks, we
            # adapt them into the detector's preferred frame length if
            # available, otherwise we pass chunks through as-is.
            frame_len = getattr(self._vad, "frame_length", None)

            if frame_len is not None and self.sample_size:
                bytes_per_frame = frame_len * self.sample_size

                # Carry over any leftover bytes from the previous call so
                # that we always feed full frames to the VAD.
                residual = cache.get("_vad_residual", b"")
                data = residual + chunk
                cache["_vad_residual"] = b""

                while len(data) >= bytes_per_frame:
                    frame_bytes = data[:bytes_per_frame]
                    data = data[bytes_per_frame:]

                    detection_result = self._vad.process(
                        frame_bytes,
                        cache=cache,
                        threshold=self._threshold,
                        pre_speech_duration=self._pre_speech_duration,
                        post_speech_duration=self._post_speech_duration,
                    )

                # Store any remaining bytes for the next chunk; we do not
                # call the VAD on partial frames to avoid shape errors.
                cache["_vad_residual"] = data
            else:
                detection_result = self._vad.process(
                    chunk,
                    cache=cache,
                    threshold=self._threshold,
                    pre_speech_duration=self._pre_speech_duration,
                    post_speech_duration=self._post_speech_duration,
                )
        elif self._detection_mode == self.DetectionMode.HOTWORD:
            audio_frame = self.convert_data(chunk)
            keyword_index = self._hotword_detector.process(audio_frame)
            detection_result = keyword_index >= 0
            if detection_result:
                self._last_hotword_detected = self.available_keywords[keyword_index]
                # Switch to voice activity detection once hotword is detected
                self.set_detection_mode(self.DetectionMode.VOICE_ACTIVITY)
            else:
                self._last_hotword_detected = None
        else:
            detection_result = False

        # Voice activity handling ---------------------------------------------
        out: List[bytes] = []
        if detection_result:
            # Speech detected
            if not speech_in_progress:
                # Start of speech: prepend pre-speech queue
                chunks = list(self._pre_speech_queue) + [chunk]
                self._pre_speech_queue.clear()
                out.extend(chunks)
            else:
                # Speech continues
                out.append(chunk)
            speech_in_progress = True
        else:
            # No speech
            if speech_in_progress:
                # End of utterance marker
                out.append(b"")
            else:
                # Still in silence; keep buffering pre-speech
                self._pre_speech_queue.append(chunk)
            speech_in_progress = False

        return speech_in_progress, out

    def generator(self) -> Iterator[bytes]:
        """Yield VAD-filtered speech chunks from the underlying audio source.

        Non-empty chunks are speech audio; `b""` marks the end of an
        utterance. This method always consumes from the wrapped source's
        `generator()`; all concrete sources must implement that method.
        """

        cache: Dict = {}
        speech_in_progress = False
        start_time = datetime.now()

        self.resume()

        try:
            source_gen = self._source.generator()
        except Exception:
            source_gen = None

        if source_gen is None:
            # No generator available; nothing we can do in the new model.
            return

        for chunk in source_gen:
            if self._closed:
                break

            if chunk is None:
                continue

            if self._timer_expired(start_time, self._detection_timeout):
                self.pause()
                raise TimeoutError("VAD detection timed out")

            speech_in_progress, out_chunks = self._process_chunk(
                chunk, cache, speech_in_progress
            )

            for out_chunk in out_chunks:
                if out_chunk == b"":
                    # End of utterance
                    yield b""
                else:
                    # Speech chunk
                    yield out_chunk

        # Ensure we end any in-progress speech with a boundary
        if speech_in_progress:
            yield b""

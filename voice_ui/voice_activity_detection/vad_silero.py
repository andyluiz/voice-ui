from typing import List, Union

import numpy as np
import silero_vad

from .vad_i import IVoiceActivityDetector


class SileroVAD(IVoiceActivityDetector):
    def __init__(self):
        self._vad_model = silero_vad.load_silero_vad(onnx=True)

    @property
    def frame_length(self) -> int:
        return 512

    @property
    def sample_rate(self) -> int:
        return 16_000

    @staticmethod
    def _convert_data_to_numpy_array(byte_data):
        output = np.frombuffer(byte_data, dtype=np.int16)
        output = output / np.iinfo(np.int16).max  # Normalize to [-1.0, 1.0]
        return output

    def process(self, data: Union[bytes, List], cache, **kwargs) -> bool:
        if isinstance(data, bytes):
            audio_frame = self._convert_data_to_numpy_array(data)
        elif isinstance(data, list):
            audio_frame = np.array(data)
        else:
            raise ValueError(f'Invalid data type: {type(data)}')

        if cache is None:
            raise ValueError('Cache is required for streaming VAD')

        if 'vad_iterator' not in cache:
            cache['vad_iterator'] = silero_vad.VADIterator(
                self._vad_model,
                threshold=kwargs.get('threshold', 0.5),
                speech_pad_ms=kwargs.get('pre_speech_duration', 0.1) * 1000,
                min_silence_duration_ms=kwargs.get('post_speech_duration', 0.5) * 1000,
            )

        if 'speech_detected' not in cache:
            cache['speech_detected'] = False

        speech_dict = cache['vad_iterator'](audio_frame, return_seconds=True)

        if not speech_dict:
            return cache['speech_detected']

        if 'start' in speech_dict:
            cache['speech_detected'] = True

        if 'end' in speech_dict:
            cache['speech_detected'] = False

        return cache['speech_detected']

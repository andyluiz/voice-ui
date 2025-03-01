import logging
from typing import List, Union

import funasr
import numpy as np

from .vad_i import IVoiceActivityDetector


class FunASRVAD(IVoiceActivityDetector):
    def __init__(self, frame_length_ms: int = 200):
        self._vad = funasr.AutoModel(model="fsmn-vad", disable_update=True)
        self._frame_length_ms = frame_length_ms

    @property
    def frame_length(self) -> int:
        return self._frame_length_ms * self.sample_rate // 1000

    @property
    def sample_rate(self) -> int:
        return 16_000

    @staticmethod
    def _convert_data_to_numpy_array(byte_data):
        output = np.frombuffer(byte_data, dtype=np.int16)
        output = output / np.iinfo(np.int16).max  # Normalize to [-1.0, 1.0]
        return output

    def process(self, data: Union[bytes, List], cache, chunk_size=None, **kwargs) -> bool:
        """
        Process the audio data and return True if speech is detected in the data interval, False otherwise.
        """
        if isinstance(data, bytes):
            audio_frame = self._convert_data_to_numpy_array(data)
        elif isinstance(data, list):
            audio_frame = np.array(data)
        else:
            raise ValueError(f'Invalid data type: {type(data)}')

        if cache is None:
            raise ValueError('Cache is required for streaming VAD')

        if 'speech_in_progress' not in cache:
            cache['speech_in_progress'] = False

        if 'vad_cache' not in cache:
            cache['vad_cache'] = {}

        if chunk_size is None:
            chunk_size = self._frame_length_ms

        # Note: The output format for the streaming VAD model can be one of four scenarios:
        # [[beg1, end1], [beg2, end2], .., [begN, endN]]：The same as the offline VAD output result mentioned above.
        # [[beg, -1]]：Indicates that only a starting point has been detected.
        # [[-1, end]]：Indicates that only an ending point has been detected.
        # []：Indicates that neither a starting point nor an ending point has been detected.
        vad_res = self._vad.generate(
            input=audio_frame,
            cache=cache['vad_cache'],
            is_final=False,
            chunk_size=chunk_size,
            disable_pbar=True,
            **kwargs,
        )

        logging.debug(f'VAD result: {vad_res}')

        if not vad_res:
            return cache['speech_in_progress']

        if not vad_res[0]['value']:
            return cache['speech_in_progress']

        value = vad_res[0]['value'][0]

        # Return true if speech is in progress, false otherwise.
        starting_point_detected = value[0] != -1
        ending_point_detected = value[1] != -1
        if starting_point_detected and not ending_point_detected:
            cache['speech_in_progress'] = True
            return True

        if not starting_point_detected and ending_point_detected:
            cache['speech_in_progress'] = False
            return True

        if starting_point_detected and ending_point_detected:
            cache['speech_in_progress'] = False
            return True

        return cache['speech_in_progress']

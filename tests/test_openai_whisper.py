import os
import unittest

import numpy as np

import voice_ui.speech_recognition.openai_whisper as ow


class FakeAudioSegment:
    def __init__(self, raw):
        self._raw = raw

    def reverse(self):
        return self

    def __len__(self):
        return 100

    def export(self, filename, format=None):
        # create a small wav file content
        # Handle both file paths (str) and BytesIO objects
        content = b'RIFF'
        if isinstance(filename, (str, bytes)):
            with open(filename, 'wb') as f:
                f.write(content)
        else:
            # Assume it's a file-like object (BytesIO)
            filename.write(content)

    def __getitem__(self, item):
        # support slicing as AudioSegment does
        return self


class FakeOpenAIClient:
    class audio:
        class transcriptions:
            @staticmethod
            def create(**kwargs):
                class R:
                    text = ' hello '

                return R()

    def __init__(self, api_key=None):
        self.audio = FakeOpenAIClient.audio()


class TestWhisperTranscriber(unittest.TestCase):
    def test_transcribe_and_calculate_rms(self):
        # Patch dependencies
        orig_OpenAI = ow.openai.OpenAI
        ow.openai.OpenAI = FakeOpenAIClient

        orig_from_raw = ow.AudioSegment.from_raw
        ow.AudioSegment.from_raw = lambda b, sample_width, frame_rate, channels: FakeAudioSegment(b)

        orig_detect = ow.silence.detect_leading_silence
        ow.silence.detect_leading_silence = lambda s: 0

        # ensure env var exists
        os.environ['OPENAI_API_KEY'] = 'x'

        try:
            t = ow.WhisperTranscriber()

            # create a fake AudioData object
            class A:
                pass

            a = A()
            a.content = b'\x00\x01' * 100
            a.sample_size = 2
            a.rate = 16000
            a.channels = 1

            res = t.transcribe(a, prompt='p')
            self.assertEqual(res, 'hello')

            # test calculate_rms with known frames
            arr = np.array([0, 32767, -32768], dtype=np.int16)
            frames = arr.tobytes()
            rms = ow.WhisperTranscriber.calculate_rms(frames)
            self.assertGreater(rms, 0)
        finally:
            ow.openai.OpenAI = orig_OpenAI
            ow.AudioSegment.from_raw = orig_from_raw
            ow.silence.detect_leading_silence = orig_detect


if __name__ == '__main__':
    unittest.main()

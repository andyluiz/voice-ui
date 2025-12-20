import sys
import types
import unittest

import numpy as np


def _inject_dummy_whisper():
    mod = types.SimpleNamespace()

    def load_model(model, device=None):
        return "dummy_model"

    def pad_or_trim(audio):
        return audio

    def transcribe(model, audio, initial_prompt=None, verbose=False):
        return {"text": "transcribed"}

    mod.load_model = load_model
    mod.pad_or_trim = pad_or_trim
    mod.transcribe = transcribe
    sys.modules["whisper_timestamped"] = mod


_inject_dummy_whisper()

from voice_ui.speech_recognition.openai_local_whisper import LocalWhisperTranscriber


class TestLocalWhisperTranscriber(unittest.TestCase):
    def test_transcribe_calls_whisper_and_returns(self):
        import voice_ui.speech_recognition.openai_local_whisper as mod

        t = LocalWhisperTranscriber.__new__(LocalWhisperTranscriber)
        t._model = mod.whisper.load_model("small")

        class A:
            pass

        audio = A()
        audio.content = np.array([0, 1, -1], dtype=np.int16)

        res = LocalWhisperTranscriber.transcribe(t, audio, prompt="p")
        self.assertEqual(res, {"text": "transcribed"})


if __name__ == "__main__":
    unittest.main()

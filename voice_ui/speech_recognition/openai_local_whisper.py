import os
import sys
from contextlib import contextmanager

import whisper_timestamped as whisper

from .speech_to_text_transcriber import AudioData, SpeechToTextTranscriber


@contextmanager
def suppress_stdout():
    # Auxiliary function to suppress Whisper logs (it is quite verbose)
    # All credit goes to: https://thesmithfam.org/blog/2012/10/25/temporarily-suppress-console-output-in-python/
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout


class LocalWhisperTranscriber(SpeechToTextTranscriber):
    def __init__(self, model="small", device=None):
        self._model = whisper.load_model(model, device=device)

    def name() -> str:
        return "local_whisper"

    def transcribe(self, audio_data: AudioData, prompt=None):
        """Transcribe audio using Whisper"""
        # Pad/trim audio to fit 30 seconds as required by Whisper
        audio = audio_data.content.astype("float32").reshape(-1)
        audio = whisper.pad_or_trim(audio)

        # Transcribe the given audio while suppressing logs
        with suppress_stdout():
            transcription = whisper.transcribe(
                self._model,
                audio,
                # We use past transcriptions to condition the model
                initial_prompt=prompt,
                verbose=True  # to avoid progress bar
            )

        return transcription

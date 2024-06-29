import os
import sys
import tempfile
import wave

import openai

try:
    from contextlib import contextmanager

    import whisper_timestamped as whisper

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

    class LocalWhisperTranscriber:
        def __init__(self, model="small", device=None):
            self.model = whisper.load_model(model, device=device)
            self._buffer = ""

        def transcribe(self, waveform):
            """Transcribe audio using Whisper"""
            # Pad/trim audio to fit 30 seconds as required by Whisper
            audio = waveform.astype("float32").reshape(-1)
            audio = whisper.pad_or_trim(audio)

            # Transcribe the given audio while suppressing logs
            with suppress_stdout():
                transcription = whisper.transcribe(
                    self.model,
                    audio,
                    # We use past transcriptions to condition the model
                    initial_prompt=self._buffer,
                    verbose=True  # to avoid progress bar
                )

            return transcription

except ImportError:
    pass


class WhisperTranscriber:
    def __init__(self):
        self._client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def transcribe(self, audio_data, **kwargs):
        """Transcribe audio using Whisper"""
        try:
            # Create a temporary file in the default temporary directory
            temp_file = tempfile.NamedTemporaryFile(prefix="speech_", suffix='.wav', delete=False)
            # Close the file
            temp_file.close()
            audio_file_name = temp_file.name

            with wave.open(audio_file_name, "wb") as wf:
                wf.setnchannels(audio_data['channels'])
                wf.setsampwidth(audio_data['sample_size'])
                wf.setframerate(audio_data['rate'])
                wf.writeframes(audio_data['content'])
                wf.close()

            with open(audio_file_name, "rb") as audio_file:
                response = self._client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    **kwargs,
                )
        finally:
            # Delete the temporary file
            os.unlink(audio_file_name)

        return response

import io
import os
import sys
import tempfile

import numpy as np
import openai
from pydub import AudioSegment, silence

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

    def transcribe(self, audio_data, **kwargs) -> openai.types.audio.TranscriptionVerbose:
        """Transcribe audio using Whisper"""
        try:
            # Create a temporary file in the default temporary directory
            temp_file = tempfile.NamedTemporaryFile(prefix="speech_", suffix='.wav', delete=False)
            # Close the file
            temp_file.close()
            audio_file_name = temp_file.name

            # Convert the audio data to a WAV file
            sound = AudioSegment.from_raw(
                io.BytesIO(audio_data['content']),
                sample_width=audio_data['sample_size'],
                frame_rate=audio_data['rate'],
                channels=audio_data['channels']
            )

            # Trim the audio to remove silence
            start_trim = silence.detect_leading_silence(sound)
            end_trim = silence.detect_leading_silence(sound.reverse())

            duration = len(sound)
            trimmed_sound = sound[start_trim:(duration - end_trim)]

            # Save the trimmed audio to a temporary file
            trimmed_sound.export(audio_file_name, format="wav")

            # Transcribe the audio using OpenAI
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

    @staticmethod
    def calculate_rms(frames):
        # Convert frames to numpy array
        audio_data = np.frombuffer(frames, dtype=np.int16)

        # Normalize the audio data
        max_amplitude = np.iinfo(np.int16).max
        normalized_audio = audio_data / max_amplitude

        # Calculate the RMS value
        rms_value = np.sqrt(np.mean(normalized_audio**2))

        return rms_value

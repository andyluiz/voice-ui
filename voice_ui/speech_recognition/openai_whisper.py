import io
import os

import numpy as np
import openai
from pydub import AudioSegment, silence

from .speech_to_text_transcriber import AudioData, SpeechToTextTranscriber


class WhisperTranscriber(SpeechToTextTranscriber):
    def __init__(self):
        self._client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def name() -> str:
        return "whisper"

    def transcribe(self, audio_data: AudioData, prompt: str = None) -> str:
        """Transcribe audio using Whisper"""
        audio_file = None
        try:
            # Convert the audio data to a WAV file
            sound = AudioSegment.from_raw(
                io.BytesIO(audio_data.content),
                sample_width=audio_data.sample_size,
                frame_rate=audio_data.rate,
                channels=audio_data.channels
            )

            # Trim the audio to remove silence
            start_trim = silence.detect_leading_silence(sound)
            end_trim = silence.detect_leading_silence(sound.reverse())

            duration = len(sound)
            trimmed_sound = sound[start_trim:(duration - end_trim)]

            # Export to a BytesIO buffer instead of a temporary file
            audio_file = io.BytesIO()
            trimmed_sound.export(audio_file, format="wav")
            audio_file.seek(0)  # Reset to beginning for reading
            # Set a name attribute so OpenAI API recognizes the format (metadata only, no file created)
            audio_file.name = "dummy_audio_file_name.wav"

            # Transcribe the audio using OpenAI
            response = self._client.audio.transcriptions.create(
                # model="whisper-1",
                model="gpt-4o-mini-transcribe",
                file=audio_file,
                # response_format="verbose_json",
                response_format="json",
                prompt=prompt,
            )

            return response.text.strip()
        finally:
            # Close the BytesIO buffer if it was created
            if audio_file is not None:
                audio_file.close()

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

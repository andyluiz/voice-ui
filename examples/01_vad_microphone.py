import os
import sys
import wave

import dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_ui.speech_detection.vad_microphone import MicrophoneVADStream

dotenv.load_dotenv()


# Main function
def main():
    stream = MicrophoneVADStream(
        # vad_engine='SileroVAD'
        # vad_engine='FunASRVAD'
        # vad_engine='PicoVoiceVAD'
    )

    try:
        print("Listening...")
        with wave.open("recorded_vad_audio.wav", "wb") as wav_file:
            wav_file.setnchannels(stream.channels)
            wav_file.setsampwidth(stream.sample_size)
            wav_file.setframerate(stream.rate)

            voice_detected = False
            for chunk in stream.generator():
                if not voice_detected:
                    voice_detected = True
                    print("Start of speech detected")

                if len(chunk) > 0:
                    wav_file.writeframes(chunk)
                else:
                    voice_detected = False
                    print("End of speech detected")

    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()

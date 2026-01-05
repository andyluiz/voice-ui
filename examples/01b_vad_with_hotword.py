import os
import sys
import wave

import dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_ui.speech_detection.vad_audio_source import VADAudioSource

dotenv.load_dotenv()


# Main function
def main():
    stream = VADAudioSource(
        # vad_engine='SileroVAD'
        # vad_engine='FunASRVAD'
        # vad_engine='PicoVoiceVAD'
    )

    try:
        print(
            "Listening for one of the following hotwords: ", stream.available_keywords
        )
        stream.set_detection_mode(VADAudioSource.DetectionMode.HOTWORD)

        with wave.open("recorded_vad_audio.wav", "wb") as wav_file:
            wav_file.setnchannels(stream.channels)
            wav_file.setsampwidth(stream.sample_size)
            wav_file.setframerate(stream.rate)

            for chunk in stream.generator():
                print(
                    f"detection_mode: {stream.detection_mode.name}, hotword: {stream.last_hotword_detected}"
                )
                if len(chunk) > 0:
                    wav_file.writeframes(chunk)
                else:
                    stream.set_detection_mode(VADAudioSource.DetectionMode.HOTWORD)
                    print("End of speech detected")

    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()

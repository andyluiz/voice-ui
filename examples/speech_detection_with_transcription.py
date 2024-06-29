import os
import sys

import dotenv
from colorama import Fore
from six.moves import queue

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_ui.speech_recognition.openai_whisper import WhisperTranscriber
from voice_ui.speech_recognition.speech_detector import (
    MetaDataEvent,
    PartialSpeechEndedEvent,
    SpeechDetector,
    SpeechEndedEvent,
    SpeechStartedEvent,
)

dotenv.load_dotenv()

whisper = WhisperTranscriber()

transcriptions = []

events = queue.Queue()


def process_event():
    # Wait for the next event
    event = events.get(timeout=1)
    audio_data = event.get("audio_data")
    metadata = event.get("metadata")

    if isinstance(event, SpeechStartedEvent):
        print(f"\n{Fore.GREEN}Speech start detected{Fore.RESET}")

    elif isinstance(event, (SpeechEndedEvent, PartialSpeechEndedEvent)):
        print(
            "\n{}Speech {} detected{}".format(
                Fore.GREEN,
                "end" if isinstance(event, SpeechEndedEvent) else "partial end",
                Fore.RESET,
            )
        )
        print(f"{Fore.BLUE}Speaker: {metadata.get('speaker')}{Fore.RESET}")

        response = whisper.transcribe(
            audio_data=audio_data,
            prompt=transcriptions[-1] if len(transcriptions) > 0 else None,
        )

        transcription = response.text

        if isinstance(event, SpeechEndedEvent) or len(transcriptions) == 0:
            transcriptions.append(transcription)
            print(transcription, end="\n\n")
        else:
            transcriptions[-1] += " " + transcription
            print(transcription)

    elif isinstance(event, MetaDataEvent):
        max_size = len("Voice Probability: {}".format(100 * "#"))
        print(
            " " * max_size
            + "\rVoice Probability: {}".format(
                int(metadata["voice_probability"] * 100) * "#"
            ),
            end="\r",
            flush=True,
        )
        pass
    else:
        raise Exception("Unknown event: {}".format(event))


# Main function
def main():
    try:
        speech_detector = SpeechDetector(
            pv_access_key=os.environ["PORCUPINE_ACCESS_KEY"],
            callback=lambda event: events.put(event),
        )

        # Detect speech
        speech_detector.start()

        while True:
            process_event()
    except queue.Empty:
        pass
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        speech_detector.stop()


if __name__ == "__main__":
    main()

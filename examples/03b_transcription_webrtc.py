import os
import sys

import dotenv
from colorama import Fore
from six.moves import queue

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_ui.audio_io.remote_microphone import RemoteMicrophone
from voice_ui.speech_detection.speech_detector import (
    MetaDataEvent,
    PartialSpeechEndedEvent,
    SpeechDetector,
    SpeechEndedEvent,
    SpeechStartedEvent,
)
from voice_ui.speech_recognition.openai_whisper import WhisperTranscriber

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

        transcription = whisper.transcribe(
            audio_data=audio_data,
            prompt=transcriptions[-1] if len(transcriptions) > 0 else None,
        )

        if isinstance(event, SpeechEndedEvent) or len(transcriptions) == 0:
            transcriptions.append(transcription)
            print(transcription, end="\n\n")
        else:
            transcriptions[-1] += " " + transcription
            print(transcription)

    elif isinstance(event, MetaDataEvent):
        # print(metadata)
        pass
    else:
        raise Exception("Unknown event: {}".format(event))


# Main function
def main():
    print("Creating remote microphone and speech detector...")
    remote_mic = RemoteMicrophone()

    speech_detector = SpeechDetector(
        on_speech_event=lambda event: events.put(event),
        source_instance=remote_mic,
    )

    # Start remote mic and detector
    remote_mic.start()
    print("Listening for speech (remote)...")
    speech_detector.start()

    while True:
        try:
            process_event()
        except queue.Empty:
            pass
        except (EOFError, KeyboardInterrupt):
            break

    print("Stopping...")
    speech_detector.stop()
    remote_mic.stop()


if __name__ == "__main__":
    main()

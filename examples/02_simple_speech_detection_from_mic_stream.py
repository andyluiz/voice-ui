import os
import sys

import dotenv
from colorama import Fore
from six.moves import queue

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_ui.speech_detection.speech_detector import (
    MetaDataEvent,
    PartialSpeechEndedEvent,
    SpeechDetector,
    SpeechEndedEvent,
    SpeechStartedEvent,
)

dotenv.load_dotenv()

# Event queue
events = queue.Queue()


# Event handler
def process_event():
    # Wait for the next event
    event = events.get(timeout=1)
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

    elif isinstance(event, MetaDataEvent):
        # print(f"metadata: {metadata}")
        pass
    else:
        raise Exception("Unknown event: {}".format(event))


# Main function
def main():
    print("Creating speech detector...")
    speech_detector = SpeechDetector(
        on_speech_event=lambda event: events.put(event),
    )

    # Detect speech
    print("Listening for speech...")
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


if __name__ == "__main__":
    main()

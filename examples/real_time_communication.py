import os
import sys

import dotenv
from colorama import Fore
from six.moves import queue

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_ui import (
    PartialSpeechEndedEvent,
    SpeechEndedEvent,
    SpeechStartedEvent,
    VoiceUI,
)

dotenv.load_dotenv()


# Main function
def main():
    # Event queue
    events = queue.Queue()

    config = {
        # 'hotword_inactivity_timeout': 30,
    }

    voice_ui = VoiceUI(
        speech_callback=lambda event: events.put(event),
        config=config,
    )

    # Event handler
    def process_event():
        # Wait for the next event
        event = events.get(timeout=1)
        text = event.get("text")

        if isinstance(event, SpeechStartedEvent):
            print(f"\n{Fore.RED}Speech start detected{Fore.RESET}")

        elif isinstance(event, PartialSpeechEndedEvent):
            print(f"\n{Fore.YELLOW}Speech partial end detected{Fore.RESET}")
            print(f"Partial text: {text}{Fore.RESET}")

        elif isinstance(event, SpeechEndedEvent):
            print(f"\n{Fore.GREEN}Speech end detected{Fore.RESET}")
            print(f"Full text: {text}{Fore.RESET}")

            # Repeat what the user said
            voice_ui.speak(text)

        else:
            print(event)

    # Detect speech
    voice_ui.start()
    print(f"{Fore.MAGENTA}Start speaking. What you say will be repeated back to you.{Fore.RESET}")
    print(f"{Fore.MAGENTA}You can interrupt at any moment by speaking over it.{Fore.RESET}")

    while True:
        try:
            process_event()
        except queue.Empty:
            pass
        except (EOFError, KeyboardInterrupt):
            break


if __name__ == "__main__":
    main()

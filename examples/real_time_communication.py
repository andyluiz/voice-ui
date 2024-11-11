import os
import sys
from datetime import datetime
from pathlib import Path

import dotenv
from colorama import Fore
from six.moves import queue

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_ui import (
    PartialSpeechEndedEvent,
    PartialTranscriptionEvent,
    SpeechEndedEvent,
    SpeechStartedEvent,
    TranscriptionEvent,
    VoiceUI,
)

dotenv.load_dotenv()


def print_event(msg):
    # Print the event and the timestamp (including milliseconds)
    now = datetime.now().strftime("%H:%M:%S.%f")
    print(f"[{now}] {msg}")


# Main function
def main():
    # Event queue
    events = queue.Queue()

    config = {
        # 'hotword_inactivity_timeout': 30,
        'voice_profiles_dir': Path(os.path.join(Path(__file__).parent, "voice_profiles")),
        'post_speech_duration': 1.0,
        'max_speech_duration': 10,
        'tts_engine': 'google',
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
            print_event(f"{Fore.RED}Speech start detected{Fore.RESET}")

        elif isinstance(event, PartialSpeechEndedEvent):
            print_event(f"{Fore.YELLOW}Speech partial end detected{Fore.RESET}")

        elif isinstance(event, SpeechEndedEvent):
            print_event(f"{Fore.GREEN}Speech end detected{Fore.RESET}")

        elif isinstance(event, PartialTranscriptionEvent):
            print_event(f"{Fore.YELLOW}Partial transcription event. Text: \"{text}\", Speaker: {event.get('speaker')}{Fore.RESET}")

        elif isinstance(event, TranscriptionEvent):
            print_event(f"{Fore.GREEN}Transcription event. Text: \"{text}\", Speaker: {event.get('speaker')}{Fore.RESET}")

            # Repeat what the user said
            voice_ui.speak(text)

        else:
            print_event(event)

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

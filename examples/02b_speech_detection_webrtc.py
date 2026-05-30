"""Simple speech detection using a simulated virtual audio source.

This example demonstrates how to:

- Capture audio from the local microphone (MicrophoneStream)
- Forward those frames into a VirtualMicrophone via push_frame()
- Run SpeechDetector on the VirtualMicrophone as if audio were coming
    from a real virtual/WebRTC peer

It is functionally similar to 02_simple_speech_detection_from_mic_stream,
but exercises the VirtualMicrophone + AudioSourceBase abstraction layer.
"""

import os
import sys
import threading

import dotenv
from colorama import Fore
from six.moves import queue

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_ui.audio_io.microphone import MicrophoneStream
from voice_ui.audio_io.virtual_microphone import VirtualMicrophone
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


# Helper to feed audio from the local microphone into the VirtualMicrophone.
def _start_mic_feeder(virtual_mic: VirtualMicrophone, mic: MicrophoneStream) -> None:
    def _run() -> None:
        try:
            mic.resume()
            for data in mic.generator():
                if not data:
                    break
                virtual_mic.push_frame(data)
        except Exception as exc:  # pragma: no cover - diagnostic only
            print(f"Error feeding microphone audio to VirtualMicrophone: {exc}")

    feeder = threading.Thread(target=_run, daemon=True)
    feeder.start()


# Main function
def main():
    print("Creating virtual microphone and speech detector...")

    # Create virtual microphone
    virtual_mic = VirtualMicrophone()

    speech_detector = SpeechDetector(
        on_speech_event=lambda event: events.put(event),
        source_instance=virtual_mic,
    )

    print(
        "Forwarding local microphone audio into VirtualMicrophone "
        "(simulating a virtual source)."
    )

    # Start feeding microphone frames into the VirtualMicrophone.
    # Local microphone used as the actual capture device.
    mic = MicrophoneStream()
    _start_mic_feeder(virtual_mic, mic)

    # Start virtual mic and detector
    virtual_mic.start()

    print("Listening for speech (virtual)...")
    speech_detector.start()

    try:
        while True:
            try:
                process_event()
            except queue.Empty:
                pass
            except (EOFError, KeyboardInterrupt):
                break
    finally:
        print("Stopping...")
        speech_detector.stop()
        mic.pause()
        virtual_mic.stop()


if __name__ == "__main__":
    main()

"""VoiceUI example using WebRTC remote audio via WebRTCRemoteMicrophone.

This example demonstrates a turnkey WebRTC audio integration using the
WebRTCRemoteMicrophone class. The class handles all WebSocket signaling,
SDP exchange, ICE candidates, and audio frame receiving automatically.

Workflow
--------
1. Install optional dependencies: ``pip install voice-ui[webrtc]``
2. Run this script: ``python 04_voiceui_webrtc_remote_audio.py``
3. Open http://127.0.0.1:8000/webrtc_sender.html in your browser and click "Start".
4. Speak into your microphone; the example will transcribe and echo back.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import dotenv
from colorama import Fore
from six.moves import queue

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_ui import (  # type: ignore
    PartialSpeechEndedEvent,
    PartialTranscriptionEvent,
    SpeechEndedEvent,
    SpeechStartedEvent,
    TranscriptionEvent,
    VoiceUI,
    VoiceUIConfig,
)
from voice_ui.config import AudioIOConfig, SpeechDetectionConfig, TextToSpeechConfig

try:
    from voice_ui.audio_io.webrtc_remote_microphone import WebRTCRemoteMicrophone

    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False


def print_event(msg: str) -> None:
    """Print an event with a timestamp."""

    now = datetime.now().strftime("%H:%M:%S.%f")
    print(f"[{now}] {msg}")


def main() -> None:
    dotenv.load_dotenv()

    # Check if WebRTC is available
    if not WEBRTC_AVAILABLE:
        print(f"{Fore.RED}Error: WebRTC components not available.{Fore.RESET}")
        print(f"{Fore.YELLOW}Install with: pip install voice-ui[webrtc]{Fore.RESET}")
        return

    # Create WebRTC microphone with built-in signaling and HTTP server
    examples_dir = Path(__file__).parent
    remote_mic = None
    try:
        remote_mic = WebRTCRemoteMicrophone(
            signaling_port=8765,
            serve_html=True,
            html_path=examples_dir / "webrtc_sender.html",
            http_port=8000,
        )
        remote_mic.start()
    except OSError as e:
        print(f"{Fore.RED}Error starting WebRTC server: {e}{Fore.RESET}")
        if "Address already in use" in str(e):
            print(
                f"{Fore.YELLOW}One of the ports (8000, 8765) is already in use.{Fore.RESET}"
            )
            print(
                f"{Fore.YELLOW}Kill the process with: kill $(lsof -ti :8000,:8765){Fore.RESET}"
            )
            print(f"{Fore.YELLOW}Or use: lsof -i :8000,:8765{Fore.RESET}")
        return
    except Exception as e:
        print(f"{Fore.RED}Error creating WebRTC microphone: {e}{Fore.RESET}")
        return

    print_event("HTTP server running at http://127.0.0.1:8000/webrtc_sender.html")
    print_event("WebSocket signaling server listening at ws://127.0.0.1:8765")

    events = queue.Queue()

    config = VoiceUIConfig(
        speech_detection=SpeechDetectionConfig(
            post_speech_duration=1.0,
            max_speech_duration=10,
            voice_profiles_dir=None,  # Disable speaker identification (Eagle version issues)
        ),
        # Use 'passthrough' to avoid TTS API key requirement, or use 'openai' if OPENAI_API_KEY is set
        text_to_speech=TextToSpeechConfig(engine="google"),
        audio_io=AudioIOConfig(audio_source_instance=remote_mic),
    )

    # Use WebRTCRemoteMicrophone as the audio source
    try:
        voice_ui = VoiceUI(
            speech_callback=lambda event: events.put(event),
            config=config,
        )
    except Exception as e:
        print(f"{Fore.RED}Error initializing VoiceUI: {e}{Fore.RESET}")
        print(
            f"{Fore.YELLOW}Check environment variables (PORCUPINE_ACCESS_KEY, OPENAI_API_KEY).{Fore.RESET}"
        )
        if remote_mic:
            remote_mic.stop()
        return

    def process_event() -> None:
        event = events.get(timeout=1)
        text = event.get("text")

        if isinstance(event, SpeechStartedEvent):
            print_event(f"{Fore.RED}Speech start detected{Fore.RESET}")

        elif isinstance(event, PartialSpeechEndedEvent):
            print_event(f"{Fore.YELLOW}Speech partial end detected{Fore.RESET}")

        elif isinstance(event, SpeechEndedEvent):
            print_event(f"{Fore.GREEN}Speech end detected{Fore.RESET}")

        elif isinstance(event, PartialTranscriptionEvent):
            print_event(
                f'{Fore.YELLOW}Partial transcription event. Text: "{text}", '
                f"Speaker: {event.get('speaker')}{Fore.RESET}"
            )

        elif isinstance(event, TranscriptionEvent):
            print_event(
                f'{Fore.GREEN}Transcription event. Text: "{text}", '
                f"Speaker: {event.get('speaker')}{Fore.RESET}"
            )
            try:
                voice_ui.speak(text)
            except Exception as e:
                print_event(f"{Fore.RED}Error speaking: {e}{Fore.RESET}")

        else:
            print_event(str(event))

    voice_ui.start()

    print(
        f"{Fore.MAGENTA}VoiceUI listening for WebRTC audio from browser. "
        f"Open http://127.0.0.1:8000/webrtc_sender.html and click 'Start'.{Fore.RESET}"
    )

    try:
        while True:
            try:
                process_event()
            except queue.Empty:
                pass
            except (EOFError, KeyboardInterrupt):
                break

    finally:
        print(f"{Fore.MAGENTA}Terminating...{Fore.RESET}")
        voice_ui.terminate()
        if remote_mic:
            remote_mic.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

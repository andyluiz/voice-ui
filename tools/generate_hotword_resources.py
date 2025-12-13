#!/usr/bin/env python3
"""
CLI tool to generate hotword resource files for testing.

Supports two modes:
1. TTS (Text-to-Speech): synthesize phrases using OpenAI, Google, or local TTS engines.
2. Record: capture microphone audio for phrases.

Output files are converted to 16 kHz mono 16-bit PCM WAV format.

Examples:
    # Generate using OpenAI TTS
    python tools/generate_hotword_resources.py --mode tts --tts-engine openai-tts \\
        --filenames hotword_alexa_keyword.wav=alexa hotword_no_keyword.wav="hello world"

    # Generate using Google TTS
    python tools/generate_hotword_resources.py --mode tts --tts-engine google \\
        --tts-params language_code=en-US \\
        --filenames hotword_computer_keyword.wav=computer

    # Record from microphone
    python tools/generate_hotword_resources.py --mode record --duration 2 \\
        --filenames hotword_recorded_keyword.wav=computer

    # List available TTS engines
    python tools/generate_hotword_resources.py --list-engines
"""

import argparse
import logging
import sys
import threading
import time
import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import dotenv
from pydub import AudioSegment

# Add parent directory to path so we can import voice_ui
sys.path.insert(0, str(Path(__file__).parent.parent))

from voice_ui.audio_io.queued_player import QueuedAudioPlayer
from voice_ui.speech_synthesis.text_to_speech_streamer_factory import TTSFactory

logger = logging.getLogger(__name__)


class AudioCapturingPlayer(QueuedAudioPlayer):
    """Custom QueuedAudioPlayer that captures audio instead of playing it."""

    def __init__(self):
        """Initialize the audio capturing player."""
        # Initialize parent without a physical player
        super().__init__(player=None)
        self._audio_chunks: List[bytes] = []
        self._lock = threading.Lock()

    def _process_queue_item(self, item: bytes) -> None:
        """
        Capture audio chunks instead of playing them.

        Args:
            item: Raw audio bytes to capture.
        """
        with self._lock:
            logger.debug(f'Capturing {len(item)} bytes of audio')
            self._audio_chunks.append(item)

    def get_captured_audio(self) -> bytes:
        """
        Get all captured audio data concatenated.

        Returns:
            Concatenated audio bytes.
        """
        with self._lock:
            return b''.join(self._audio_chunks)

    def clear(self) -> None:
        """Clear captured audio."""
        with self._lock:
            self._audio_chunks.clear()


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def normalize_audio_to_16k_mono_16bit(audio: AudioSegment) -> AudioSegment:
    """Normalize AudioSegment to 16 kHz mono 16-bit PCM using pydub."""
    # Ensure mono
    if audio.channels != 1:
        logger.debug(f"Converting {audio.channels} channels to 1 (mono)")
        audio = audio.set_channels(1)

    # Ensure 16-bit
    if audio.sample_width != 2:
        logger.debug("Converting sample width to 16-bit")
        audio = audio.set_sample_width(2)

    # Resample if needed
    if audio.frame_rate != 16000:
        logger.debug(f"Resampling from {audio.frame_rate} Hz to 16000 Hz")
        audio = audio.set_frame_rate(16000)

    # Return the normalized AudioSegment
    return audio


def generate_with_tts(
    tts_engine: str,
    filenames_map: Dict[str, str],
    tts_params: Dict[str, str],
    output_dir: Path,
    force: bool = False,
    dry_run: bool = False,
) -> bool:
    """Generate resource files using TTS via the factory with audio capture."""
    dotenv.load_dotenv()

    # Create custom audio-capturing player
    capturing_player = AudioCapturingPlayer()

    # Create TTS instance via factory with the capturing player
    try:
        tts_instance = TTSFactory.create(tts_engine, queued_player=capturing_player)
        logger.info(f"Created TTS engine: {tts_engine} with audio capture")
    except RuntimeError as e:
        logger.error(f"TTS engine '{tts_engine}' not available: {e}")
        logger.info("Available engines:")
        for name in TTSFactory.list_engines():
            logger.info(f"  - {name}")
        return False

    output_dir.mkdir(parents=True, exist_ok=True)

    for filename, phrase in filenames_map.items():
        output_path = output_dir / filename

        if output_path.exists() and not force:
            logger.warning(f"File already exists: {output_path}. Use --force to overwrite.")
            continue

        logger.info(f"Generating: {filename} (phrase: '{phrase}')")

        if dry_run:
            logger.info(f"  [DRY RUN] Would save to: {output_path}")
            continue

        try:
            # Clear previous audio
            capturing_player.clear()

            # Generate audio via TTS
            logger.debug(f"Calling speak() with phrase: '{phrase}'")
            tts_instance.speak(phrase, **tts_params)

            # Wait for playback to complete
            logger.debug("Waiting for audio generation to complete...")
            timeout = 30  # 30 second timeout
            start_time = time.time()
            while tts_instance.is_speaking():
                if time.time() - start_time > timeout:
                    logger.error(f"Timeout waiting for TTS generation of '{phrase}'")
                    return False
                time.sleep(0.1)

            # Give a bit of time for the last chunks to be processed
            time.sleep(0.2)

            # Get captured audio
            captured_audio = capturing_player.get_captured_audio()

            if not captured_audio:
                logger.error(f"No audio captured for '{phrase}'")
                return False

            logger.debug(f"Captured {len(captured_audio)} bytes of raw PCM audio")

            # Construct an AudioSegment from the captured raw PCM frames
            # OpenAI TTS produces 24 kHz mono 16-bit PCM
            logger.debug("Constructing AudioSegment from captured PCM...")
            audio = AudioSegment(
                captured_audio,
                frame_rate=24000,
                sample_width=2,
                channels=1
            )

            # Normalize to 16 kHz mono 16-bit PCM
            logger.debug("Normalizing audio to 16 kHz mono 16-bit...")
            normalized_audio = normalize_audio_to_16k_mono_16bit(audio)

            # Save to file using pydub
            logger.debug(f"Exporting audio to {output_path}")
            normalized_audio.export(str(output_path), format='wav')

            logger.info(f"  Saved: {output_path} ({len(captured_audio)} bytes)")

        except Exception as e:
            logger.error(f"Error generating {filename}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    tts_instance.terminate()
    capturing_player.terminate()
    return True


def generate_with_microphone(
    filenames_map: Dict[str, str],
    output_dir: Path,
    duration: float = 2.0,
    device_index: Optional[int] = None,
    force: bool = False,
    dry_run: bool = False,
) -> bool:
    """Generate resource files by recording from microphone."""
    from voice_ui.audio_io.microphone import MicrophoneStream

    output_dir.mkdir(parents=True, exist_ok=True)

    for filename, phrase in filenames_map.items():
        output_path = output_dir / filename

        if output_path.exists() and not force:
            logger.warning(f"File already exists: {output_path}. Use --force to overwrite.")
            continue

        logger.info(f"Recording: {filename}")
        logger.info(f"  Phrase: '{phrase}'")
        logger.info(f"  Duration: {duration}s")

        if dry_run:
            logger.info(f"  [DRY RUN] Would save to: {output_path}")
            continue

        logger.info("  Press Enter when ready, then speak the phrase...")

        try:
            input("Press Enter to start recording...")

            with MicrophoneStream(rate=16000) as stream:
                # Record audio for the specified duration
                audio_data = b''
                start_time = time.time()

                for chunk in stream.generator():
                    audio_data += chunk
                    elapsed = time.time() - start_time
                    if elapsed % 0.5 < 0.05:  # Print every ~0.5 seconds
                        print(f"  Recorded {elapsed:.1f}s...", end='\r')

                    if elapsed >= duration:
                        break

            # Save to WAV file
            with wave.open(str(output_path), 'wb') as wf:
                wf.setnchannels(1)  # Mono
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(16000)  # 16 kHz
                wf.writeframes(audio_data)

            logger.info(f"  Saved: {output_path}")

        except KeyboardInterrupt:
            logger.warning(f"Recording cancelled for {filename}.")
            return False
        except Exception as e:
            logger.error(f"Error recording {filename}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    return True


def list_tts_engines() -> bool:
    """List available TTS engines."""
    print("Available TTS engines:")
    for name in TTSFactory.list_engines():
        print(f"  - {name}")
    return True


def parse_filenames_arg(arg: str) -> Tuple[str, str]:
    """Parse 'filename=phrase' argument."""
    parts = arg.split('=', 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid filename arg: {arg}. Expected format: filename=phrase")
    return parts[0], parts[1]


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        '--mode',
        choices=['tts', 'record'],
        help='Generation mode: TTS or microphone recording',
    )
    parser.add_argument(
        '--tts-engine',
        default='openai-tts',
        help='TTS engine to use (default: openai-tts). See --list-engines.',
    )
    parser.add_argument(
        '--tts-params',
        action='append',
        default=[],
        help='Additional TTS parameters as KEY=VALUE (repeatable).',
    )
    parser.add_argument(
        '--filenames',
        action='append',
        default=[],
        dest='filenames_args',
        help='Output filename and phrase: filename=phrase (repeatable). Example: --filenames hotword_alexa.wav=alexa',
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('tests/resources/hotword'),
        help='Output directory (default: tests/resources/hotword)',
    )
    parser.add_argument(
        '--duration',
        type=float,
        default=2.0,
        help='Recording duration in seconds (default: 2.0, record mode only)',
    )
    parser.add_argument(
        '--device-index',
        type=int,
        default=None,
        help='Microphone device index (record mode only). Omit to use default device.',
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing files.',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually generating files.',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging.',
    )
    parser.add_argument(
        '--list-engines',
        action='store_true',
        help='List available TTS engines and exit.',
    )

    args = parser.parse_args()

    setup_logging(args.verbose)

    if args.list_engines:
        return 0 if list_tts_engines() else 1

    if not args.mode:
        parser.error("--mode is required (unless --list-engines is used)")

    # Parse filenames
    filenames_map = {}
    for arg in args.filenames_args:
        filename, phrase = parse_filenames_arg(arg)
        filenames_map[filename] = phrase

    if not filenames_map:
        parser.error("At least one --filenames argument is required")

    logger.info(f"Mode: {args.mode}")
    logger.info(f"Output dir: {args.output_dir}")
    logger.info(f"Files to generate: {len(filenames_map)}")

    if args.mode == 'tts':
        # Parse TTS params
        tts_params = {}
        for param_arg in args.tts_params:
            key, val = param_arg.split('=', 1)
            tts_params[key] = val

        success = generate_with_tts(
            args.tts_engine,
            filenames_map,
            tts_params,
            args.output_dir,
            force=args.force,
            dry_run=args.dry_run,
        )
    else:  # record
        success = generate_with_microphone(
            filenames_map,
            args.output_dir,
            duration=args.duration,
            device_index=args.device_index,
            force=args.force,
            dry_run=args.dry_run,
        )

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())

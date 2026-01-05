<!-- GitHub Copilot / AI agent instructions for the voice-ui repo -->
# Voice UI — Copilot Instructions

This file gives concise, actionable knowledge for AI coding agents to be immediately productive in this repository.

## Repository Layout & Architecture

**Package Structure** (`voice_ui/` main package):
   - `audio_io/` — audio I/O abstractions and integrations:
     - Microphone capture: `microphone.py`, `virtual_microphone.py`
     - Audio playback: `player.py`, `virtual_player.py`
     - WebRTC integration: `webrtc_signaling_server.py`, `webrtc_remote_microphone.py`, `webrtc_remote_player.py`
     - Factories and utilities: `audio_source_factory.py`, `audio_sink_factory.py`, `audio_data.py`
- `voice_activity_detection/` — VAD engines + factory pattern (`vad_factory.py` registers engines: `SileroVAD`, `FunASRVAD`, `PicoVoiceVAD`)
- `speech_detection/` — high-level speech detection & speaker profiling (`speech_detector.py` uses VAD + hotword detection; `speaker_profile_manager.py` for speaker identification)
- `speech_recognition/` — STT transcribers + factory (`speech_to_text_transcriber_factory.py` registers: `OpenAIWhisper`, `LocalWhisper`, etc.)
- `speech_synthesis/` — TTS streamers + factory (`text_to_speech_streamer_factory.py` registers: `OpenAITextToSpeechAudioStreamer`, `GoogleTextToSpeechAudioStreamer`, `PassThroughTextToSpeechAudioStreamer`)
- `voice_ui.py` — orchestrates input/output, transcription, and hotword detection at application level

**Examples & Tests**:
- `examples/` — runnable scripts showing real-time VAD/STT/TTS flows (numbered 01-04, RT API variants)
- `tests/` — offline unit tests (default), integration tests (`integrated_test_*.py`, requires API keys), and functional tests (`tests/functional/`)
- `tests/helpers/` — shared test utilities (e.g., `audio_utils.py` for generating test audio)

## Factory Pattern (Critical for Extensibility)

Three core factories enable pluggable backends without modifying core code:

1. **VADFactory** (`voice_ui/voice_activity_detection/vad_factory.py`):
   - Classes implement `IVoiceActivityDetector` interface
   - Register at module load via `VADFactory.register_vad(name, class)` in `__init__.py`
   - Used by `SpeechDetector` to detect speech regions
   - Optional dependencies: `torch` (Silero), `funasr` (FunASR), etc.

2. **TranscriberFactory** (`voice_ui/speech_recognition/speech_to_text_transcriber_factory.py`):
   - Classes extend `SpeechToTextTranscriber` base, implement `transcribe(audio_data, prompt='')`
   - Register via `TranscriberFactory.register_transcriber(name, class)`
   - Used by `VoiceUI` for speech-to-text conversion

3. **TTSFactory** (`voice_ui/speech_synthesis/text_to_speech_streamer_factory.py`):
   - Classes extend `TextToSpeechAudioStreamer` base, implement `speak(text, voice=None)` and `terminate()`
   - Register via `TTSFactory.register_tts(name, class)`
   - Engines include OpenAI, Google Cloud, and a pass-through stub for testing

**When adding a new backend**: Create a class implementing the interface, add it to the factory registration (in the submodule's code), and ensure optional dependencies are listed in `pyproject.toml`.

## Setup & Configuration

**System Dependencies** (Ubuntu/Debian):
```bash
sudo apt install libjack-jackd2-dev portaudio19-dev
```

**Python Environment**:
```bash
make venv && source .venv/bin/activate
```

**Environment Variables** (create `.env` or export):
- `OPENAI_API_KEY` — for OpenAI TTS/STT
- `PORCUPINE_ACCESS_KEY` — for Picovoice hotword detection
- `GOOGLE_PROJECT_ID` and `GOOGLE_APPLICATION_CREDENTIALS` — for Google Cloud integrations

**Optional Dependency Groups** (in `pyproject.toml`):
Install as needed: `pip install .[openai,google,silero]` or use `make venv` (installs `requirements.txt` only; add extras manually).

## Test Organization & Running

| Test Type | Command | Requires | Purpose |
|-----------|---------|----------|---------|
| **Unit** (offline, default) | `make tests` | None | Fast feedback; mocked APIs |
| **Functional** (offline) | `make functional_tests` | None | Integration of subsystems without real APIs |
| **Online Integration** | `make online_tests` | API keys, network | Real cloud providers, hardware |
| **Single module** | `make test TEST_FILE=tests/path/to/file.py` | Varies | Isolated testing during dev |

**Coverage**: Makefile enforces `--fail-under=90` coverage. HTML report in `htmlcov/` after `make tests`.

## Development Workflows & Patterns

**Linting**:
- `make flake8` checks code style
- Dev extras in `pyproject.toml`: `black`, `flake8`, `isort`
- Apply manually or integrate into your editor

**Conventions**:
- All tests use `unittest` (not pytest). Discovery: files in `tests/` matching `test_*.py`
- Integration tests use `integrated_test_*.py` pattern (gated, requires secrets)
- Functional tests: `tests/functional/test_*.py` (offline, CI-friendly)
- When adding tests for new integrations: name them `integrated_test_<feature>.py` if they need external resources

**Creating New Examples**:
- Examples show realistic flows end-to-end. Number them (01, 02, etc.) if creating a series
- Use `examples/04_voiceui_real_time_communication.py` as template for full orchestration
- Simpler patterns in `examples/01_vad_microphone.py` (VAD only) and `examples/02_simple_speech_detection_from_mic_stream.py` (detector + STT)

**API Stability**:
- Keep public exports in `voice_ui/__init__.py` stable (e.g., `VoiceUI`, `SpeechDetector`, `SpeechEvent` classes)
- Refactor internal modules freely, but coordinate changes to public signatures

## Key Files for Architecture Understanding

- **SpeechDetector** (`voice_ui/speech_detection/speech_detector.py`): coordinates VAD + hotword + speaker profiling; emits events
- **VoiceUI** (`voice_ui/voice_ui.py`): high-level orchestrator; uses SpeechDetector + TranscriberFactory + TTSFactory
- **Factory Classes** (3 files above): registration + creation patterns; study these before extending the system
- **VirtualMicrophone** (`voice_ui/audio_io/virtual_microphone.py`): queue-based microphone for programmatic audio injection; foundation for WebRTC and testing
- **WebRTC Integration** (`voice_ui/audio_io/webrtc_*.py`): generic signaling server + specialized microphone/player classes for bidirectional audio
- **Example 04** (`examples/04_voiceui_real_time_communication.py`): full workflow with event handling and transcription

## WebRTC Architecture Notes

The WebRTC implementation uses a **generic signaling server** (`WebRTCSignalingServer`) decoupled from transport direction:

1. **Receiving audio**: `WebRTCRemoteMicrophone` extends `VirtualMicrophone` and attaches an audio track handler to the signaling server
2. **Sending audio**: `WebRTCRemotePlayer` creates custom audio generator tracks and adds them to peer connections
3. **Reusability**: Both use the same `WebRTCSignalingServer` with different `on_peer` callbacks, enabling future extensions (recording, mixing, etc.)

This design avoids code duplication and makes it easy to add new WebRTC features without reimplementing signaling logic.

## Quick Start for Agents

```bash
# Set up environment
make venv
source .venv/bin/activate

# Run fast offline tests
make tests

# Run a simple example (VAD only, no API key needed)
python examples/01_vad_microphone.py

# Run full example (requires OPENAI_API_KEY)
export OPENAI_API_KEY=sk-...
python examples/04_voiceui_real_time_communication.py

# Test a single module
make test TEST_FILE=tests/test_vad_factory.py
```

## Current State & Branch Notes

- **Branch**: `reorganize_speech_detector` introduces refactored `SpeechDetector` with cleaner VAD/hotword separation
- **Recent changes**: Factory classes → class-based API (not functions); optional dependency registration at module load
- **In-progress work** (see `TODO.md`): hotword detection interface + factory, voice profile manager interface, configuration class for `VoiceUI`

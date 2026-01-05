# AI Agent Guide for Voice UI Repository

This document provides comprehensive guidance for AI coding assistants (like GitHub Copilot, Claude, etc.) working with
the Voice UI repository. It complements the `.github/copilot-instructions.md` file with deeper context about patterns,
conventions, and best practices.

## Repository Overview

**Voice UI** is a modular Python library for building voice-driven interfaces with support for:

- Voice Activity Detection (VAD) using multiple backends (Silero, FunASR, Picovoice)
- Speech-to-Text (STT) transcription (OpenAI Whisper, local Whisper, etc.)
- Text-to-Speech (TTS) streaming (OpenAI, Google Cloud, pass-through)
- Real-time audio processing with microphone input and playback
- Hotword detection and speaker profiling

**Current Branch**: `reorganize_speech_detector` — introduces refactored `SpeechDetector` with cleaner VAD/hotword
separation.

## Key Architectural Patterns

### 1. Factory Pattern (Core Extensibility Mechanism)

The repository uses three factory classes to enable pluggable backends:

#### VADFactory

- **Location**: `voice_ui/voice_activity_detection/vad_factory.py`
- **Interface**: `IVoiceActivityDetector`
- **Registration**: Backends register via `VADFactory.register_vad(name, class)` in module `__init__.py`
- **Implementations**: `SileroVAD`, `FunASRVAD`, `PicoVoiceVAD`
- **Usage**: `SpeechDetector` uses VAD instances to detect speech regions

#### TranscriberFactory

- **Location**: `voice_ui/speech_recognition/speech_to_text_transcriber_factory.py`
- **Base Class**: `SpeechToTextTranscriber`
- **Key Method**: `transcribe(audio_data, prompt='')` → transcription text
- **Registration**: `TranscriberFactory.register_transcriber(name, class)`
- **Implementations**: `OpenAIWhisper`, `LocalWhisper`, etc.
- **Usage**: `VoiceUI` uses transcribers for speech-to-text conversion

#### TTSFactory

- **Location**: `voice_ui/speech_synthesis/text_to_speech_streamer_factory.py`
- **Base Class**: `TextToSpeechAudioStreamer`
- **Key Methods**: `speak(text, voice=None)`, `terminate()`
- **Registration**: `TTSFactory.register_tts(name, class)`
- **Implementations**: `OpenAITextToSpeechAudioStreamer`, `GoogleTextToSpeechAudioStreamer`,
  `PassThroughTextToSpeechAudioStreamer`
- **Usage**: `VoiceUI` uses TTS for audio output

**Adding New Backends**:

1. Create a class implementing the appropriate interface
2. Add factory registration in the submodule's `__init__.py`
3. List optional dependencies in `pyproject.toml` under `[project.optional-dependencies]`
4. Document any required environment variables

### 2. Event-Driven Architecture

The system uses event classes for asynchronous communication:

**Speech Detection Events** (`voice_ui/speech_detection/speech_detector.py`):

- `SpeechEvent` (base class)
- `MetaDataEvent` — contextual information
- `SpeechStartedEvent` — speech begins
- `PartialSpeechEndedEvent` — intermediate speech segment
- `SpeechEndedEvent` — complete speech utterance

**VoiceUI Events** (`voice_ui/voice_ui.py`):

- `WaitingForHotwordEvent` — listening for activation word
- `HotwordDetectedEvent` — hotword recognized
- `PartialTranscriptionEvent` — streaming transcription fragment
- `TranscriptionEvent` — complete transcription result

**Pattern**: Components yield events to callbacks/handlers. See `examples/04_voiceui_real_time_communication.py` for
full event handling patterns.

### 3. Audio Pipeline Architecture

```plain
Audio Input → VAD → SpeechDetector → Transcriber → VoiceUI
    ↓
  Sources:
  - MicrophoneStream (device audio)
  - VirtualMicrophone (programmatic injection)
  - WebRTCRemoteMicrophone (WebRTC peer)
    
Audio Output → Player Sinks:
  - Player (device playback)
  - VirtualPlayer (queue-based)
  - WebRTCRemotePlayer (WebRTC streaming)
```

**Core Classes**:

- `AudioData` (`audio_io/audio_data.py`) — immutable audio buffer with metadata
- `MicrophoneStream` (`audio_io/microphone.py`) — captures audio from device
- `VirtualMicrophone` (`audio_io/virtual_microphone.py`) — queue-based audio injection for testing/synthetic sources
- `WebRTCRemoteMicrophone` (`audio_io/webrtc_remote_microphone.py`) — autonomous WebRTC audio receiver
- `Player` (`audio_io/player.py`) — plays audio output to device
- `VirtualPlayer` (`audio_io/virtual_player.py`) — queue-based audio sink for programmatic handling
- `WebRTCRemotePlayer` (`audio_io/webrtc_remote_player.py`) — sends audio to WebRTC peers
- `SpeechDetector` (`speech_detection/speech_detector.py`) — orchestrates VAD + hotword + profiling
- `VoiceUI` (`voice_ui.py`) — high-level orchestrator for full voice interaction

## Development Guidelines for Agents

### Code Organization Principles

1. **Keep Public API Stable**: Exports in `voice_ui/__init__.py` define the public interface
2. **Factory Registration at Module Load**: Backends self-register when imported
3. **Optional Dependencies**: All cloud integrations and ML backends are optional extras
4. **Interface-First Design**: Define interfaces before implementations

### Testing Strategy

| Test Type                | Command                             | Pattern                      | Purpose                    |
|--------------------------|-------------------------------------|------------------------------|----------------------------|
| **Unit Tests** (default) | `make tests`                        | `test_*.py`                  | Fast feedback, mocked APIs |
| **Functional Tests**     | `make functional_tests`             | `tests/functional/test_*.py` | Offline integration        |
| **Online Integration**   | `make online_tests`                 | `integrated_test_*.py`       | Real APIs, requires keys   |
| **Single Module**        | `make test TEST_FILE=tests/path.py` | Any test file                | Isolated debugging         |

**Coverage Requirements**: Minimum 75% coverage enforced by Makefile.

**Test Conventions**:

- Use `unittest` framework (not pytest)
- Mock external APIs in unit tests
- Name integration tests `integrated_test_*.py` (gated, requires secrets)
- Place functional tests in `tests/functional/` (offline, CI-friendly)
- Use `tests/helpers/audio_utils.py` for generating test audio

### Environment Setup for Agents

```bash
# System dependencies (Ubuntu/Debian)
sudo apt install libjack-jackd2-dev portaudio19-dev

# Virtual environment
make venv
source .venv/bin/activate

# Install optional extras (as needed)
pip install .[openai,google,silero]

# Set environment variables
export OPENAI_API_KEY=sk-...
export PORCUPINE_ACCESS_KEY=...
export GOOGLE_PROJECT_ID=...
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/creds.json
```

### Common Development Tasks

#### Adding a New VAD Backend

1. Create class implementing `IVoiceActivityDetector` in `voice_ui/voice_activity_detection/`
2. Implement required methods: `process_chunk()`, `reset()`
3. Register in `voice_ui/voice_activity_detection/__init__.py`:

   ```python
   from .vad_my_backend import MyBackendVAD
   VADFactory.register_vad("my_backend", MyBackendVAD)
   ```

4. Add optional dependencies to `pyproject.toml`:

   ```toml
   my-backend = ["my-backend-package>=1.0.0"]
   ```

5. Create unit tests in `tests/test_vad_my_backend.py`
6. Update documentation

#### Adding a New Transcriber

1. Create class extending `SpeechToTextTranscriber` in `voice_ui/speech_recognition/`
2. Implement `transcribe(audio_data, prompt='')` method
3. Register in factory within module's code
4. Follow same dependency and testing pattern as VAD backends

#### Creating New Examples

1. Number sequentially (01, 02, 03...) for series
2. Show realistic end-to-end flows
3. Use descriptive names: `XX_feature_description.py`
4. Include comments explaining setup requirements (API keys, hardware)
5. Reference `examples/04_voiceui_real_time_communication.py` as template

### Code Style & Linting

- **Linting**: `make flake8` before committing
- **Formatter**: Use `black` (in dev extras)
- **Import Sorting**: Use `isort` (in dev extras)
- **Line Length**: Follow PEP 8 (79-99 chars typical)
- **Docstrings**: Use Google-style docstrings for public APIs

### File Naming Conventions

- Unit tests: `test_<module_name>.py`
- Integration tests: `integrated_test_<feature>.py`
- Functional tests: `tests/functional/test_<feature>.py`
- Examples: `##_descriptive_name.py` (numbered)
- Factories: `<component>_factory.py`
- Interfaces: `i_<component>.py` or `<component>_i.py`

## Current Development Focus

From `TODO.md` and recent commits:

### In Progress

1. **Hotword Detector Refactoring**:
   - Move `HotwordDetector` to dedicated file
   - Define standardized return types (keyword name, probability array)
   - Implement interface and factory pattern

2. **Voice Profile Manager**:
   - Implement interface and factory
   - Add new speaker identifier backends

3. **Functional Testing Expansion**:
   - Create offline tests for VAD, TTS, STT, and speech detection
   - Ensure CI-friendly without API dependencies

### Architecture Notes

- Branch `reorganize_speech_detector` restructures `SpeechDetector` for better separation of concerns
- Factory pattern migration from function-based to class-based API complete
- Optional dependency registration happens at module import time

## Quick Reference: Key Files

### Core Orchestration

- `voice_ui/voice_ui.py` — High-level VoiceUI class
- `voice_ui/speech_detection/speech_detector.py` — VAD + hotword coordinator
- `voice_ui/config.py` — Configuration dataclass

### Factories

- `voice_ui/voice_activity_detection/vad_factory.py`
- `voice_ui/speech_recognition/speech_to_text_transcriber_factory.py`
- `voice_ui/speech_synthesis/text_to_speech_streamer_factory.py`

### Audio I/O

- `voice_ui/audio_io/microphone.py` — Device microphone capture
- `voice_ui/audio_io/virtual_microphone.py` — Programmatic audio injection
- `voice_ui/audio_io/webrtc_remote_microphone.py` — WebRTC audio reception
- `voice_ui/audio_io/player.py` — Device audio playback
- `voice_ui/audio_io/virtual_player.py` — Queue-based audio sink
- `voice_ui/audio_io/webrtc_remote_player.py` — WebRTC audio transmission
- `voice_ui/audio_io/audio_data.py` — Audio data structure
- `voice_ui/audio_io/webrtc_signaling_server.py` — Generic WebRTC signaling (reusable for send/receive)

### Examples

- `examples/01_vad_microphone.py` — Simple VAD
- `examples/02_simple_speech_detection_from_mic_stream.py` — Detection + STT
- `examples/03_speech_detection_with_transcription.py` — Full pipeline
- `examples/04_voiceui_real_time_communication.py` — Complete real-time system

### Testing

- `tests/helpers/audio_utils.py` — Test audio generation utilities
- `tests/functional/` — Offline integration tests
- `integrated_test_*.py` — Online tests (gated)

## Dependencies Overview

### Core (Always Installed)

- `pyaudio` — Audio I/O
- `pvporcupine`, `pvrecorder`, `pveagle` — Picovoice components
- `pydub`, `sox` — Audio processing
- `python-dotenv` — Environment configuration
- `colorama` — Terminal output

### Optional Extras (Install as `pip install .[extra_name]`)

- `openai` — OpenAI API integration (STT/TTS)
- `google` — Google Cloud Speech/TTS
- `local-whisper` — Local Whisper transcription
- `silero` — Silero VAD (requires torch)
- `funasr` — FunASR VAD (requires torch)
- `pvcobra` — Picovoice Cobra VAD
- `test` — Coverage tools
- `dev` — Linting and formatting (black, flake8, isort)

## Best Practices for AI Agents

### When Reading Code

1. **Start with interfaces and factories** to understand extension points
2. **Check `__init__.py` exports** to identify public API
3. **Read examples** to understand typical usage patterns
4. **Use symbolic tools** (if available) to navigate class hierarchies
5. **Check `pyproject.toml`** for optional dependencies before suggesting features

### When Writing Code

1. **Implement interfaces, not concrete dependencies** (follow factory pattern)
2. **Add tests** for all new functionality (minimum 75% coverage)
3. **Document environment variables** required by new integrations
4. **Update `pyproject.toml`** with new optional dependencies
5. **Create examples** for significant new features
6. **Follow existing naming patterns** (factories, tests, examples)

### When Refactoring

1. **Preserve public API** in `voice_ui/__init__.py`
2. **Run full test suite** before and after (`make tests`)
3. **Update factories** if interfaces change
4. **Check example compatibility** — examples should continue working
5. **Update documentation** in README.md and docstrings

### When Debugging

1. **Check environment variables** are set correctly (`.env` file)
2. **Verify optional dependencies** are installed
3. **Run specific test** with `make test TEST_FILE=...`
4. **Enable verbose logging** in examples (most have debug flags)
5. **Test with simple examples first** (01, 02) before complex ones (04)

## Common Pitfalls to Avoid

1. **Don't modify factory registration after module load** — registration is static
2. **Don't assume optional dependencies are available** — check imports with try/except
3. **Don't use pytest** — repository uses unittest framework
4. **Don't create integration tests without gating** — use `integrated_test_*.py` pattern
5. **Don't break audio pipeline immutability** — `AudioData` objects are immutable
6. **Don't skip system dependencies** — PortAudio/JACK are required for audio I/O
7. **Don't batch event handling** — process events individually for responsiveness

## Resources

- **Primary Documentation**: `README.md`, `.github/copilot-instructions.md`
- **Architecture Diagrams**: `docs/diagram.pu` (PlantUML)
- **Configuration Reference**: `voice_ui/config.py` (dataclass with defaults)
- **Task Tracking**: `TODO.md` (current development priorities)
- **License**: MIT License (see `LICENSE` file)

## Support & Contact

- **Maintainer**: Anderson Silva (<andyluiz@yahoo.com>)
- **Repository**: voice-ui (owner: andyluiz)
- **Version**: 0.0.1 (Alpha)
- **Python Support**: 3.8+

---

**For AI Agents**: This repository follows a clean architecture with factory patterns for extensibility. When in doubt,
study the existing factories and examples before implementing new features. Always maintain backward compatibility with
the public API in `voice_ui/__init__.py`.

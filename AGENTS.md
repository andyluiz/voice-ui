# AI Agent Guide for Voice UI Repository

This document provides comprehensive guidance for AI coding assistants (like GitHub Copilot, Claude, etc.) to be immediately productive in the Voice UI repository.

## Repository Overview

**Voice UI** is a modular Python library for building voice-driven interfaces with support for:

- Voice Activity Detection (VAD) using multiple backends (Silero, FunASR, Picovoice)
- Speech-to-Text (STT) transcription (OpenAI Whisper, local Whisper, etc.)
- Text-to-Speech (TTS) streaming (OpenAI, Google Cloud, pass-through)
- Real-time audio processing with microphone input and playback
- Hotword detection and speaker profiling
- WebRTC integration for remote audio streaming

**Current Branch**: `prepare_for_web_ui` — preparing the library for web-based interfaces.

**Version**: 0.0.1 (Alpha)
**Python Support**: 3.8+
**Maintainer**: Anderson Silva (<andyluiz@yahoo.com>)
**License**: MIT License

## Repository Structure

**Package Structure** (`voice_ui/` main package):

- `audio_io/` — audio I/O abstractions and integrations:
  - Microphone capture: `microphone.py`, `virtual_microphone.py`
  - Audio playback and sinks: `audio_sink.py` (defines `AudioSink`), `player.py` (PyAudio `Player` implements `AudioSink`), `virtual_player.py`
  - WebRTC integration: `webrtc_signaling_server.py`, `webrtc_remote_microphone.py`, `webrtc_remote_player.py`
  - Factories and utilities: `audio_source_factory.py`, `audio_sink_factory.py`, `audio_data.py`
- `voice_activity_detection/` — VAD engines + factory pattern (`vad_factory.py` registers engines: `SileroVAD`, `FunASRVAD`, `PicoVoiceVAD`)
- `speech_detection/` — high-level speech detection & speaker profiling (`speech_detector.py` uses VAD + hotword detection; `speaker_profile_manager.py` for speaker identification)
- `speech_recognition/` — STT transcribers + factory (`speech_to_text_transcriber_factory.py` registers: `OpenAIWhisper`, `LocalWhisper`, etc.)
- `speech_synthesis/` — TTS streamers + factory (`text_to_speech_streamer_factory.py` registers: `OpenAITextToSpeechAudioStreamer`, `GoogleTextToSpeechAudioStreamer`, `PassThroughTextToSpeechAudioStreamer`)
- `voice_ui.py` — orchestrates input/output, transcription, and hotword detection at application level
- `config.py` — Configuration dataclass with defaults

**Examples & Tests**:

- `examples/` — runnable scripts showing real-time VAD/STT/TTS flows (numbered 01-05, with WebRTC and RT API variants)
- `tests/` — offline unit tests (default), integration tests (`integrated_test_*.py`, requires API keys), and functional tests (`tests/functional/`)
- `tests/helpers/` — shared test utilities (e.g., `audio_utils.py` for generating test audio)

## Key Architectural Patterns

### 1. Factory Pattern (Core Extensibility Mechanism)

The repository uses three factory classes to enable pluggable backends:

#### VADFactory

- **Location**: `voice_ui/voice_activity_detection/vad_factory.py`
- **Interface**: `IVoiceActivityDetector`
- **Registration**: Backends register via `VADFactory.register_vad(name, class)` in module `__init__.py`
- **Implementations**: `SileroVAD`, `FunASRVAD`, `PicoVoiceVAD`
- **Usage**: `SpeechDetector` uses VAD instances to detect speech regions
- **Optional dependencies**: `torch` (Silero), `funasr` (FunASR), etc.

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
- **Implementations**: `OpenAITextToSpeechAudioStreamer`, `GoogleTextToSpeechAudioStreamer`, `PassThroughTextToSpeechAudioStreamer`
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

**Pattern**: Components yield events to callbacks/handlers. See `examples/04_voiceui_local.py` and `examples/04b_voiceui_webrtc.py` for full event handling patterns.

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

### 4. WebRTC Architecture

The WebRTC implementation uses a **generic signaling server** (`WebRTCSignalingServer`) decoupled from transport direction:

1. **Receiving audio**: `WebRTCRemoteMicrophone` extends `VirtualMicrophone` and attaches an audio track handler to the signaling server
2. **Sending audio**: `WebRTCRemotePlayer` creates custom audio generator tracks and adds them to peer connections
3. **Reusability**: Both use the same `WebRTCSignalingServer` with different `on_peer` callbacks, enabling future extensions (recording, mixing, etc.)

This design avoids code duplication and makes it easy to add new WebRTC features without reimplementing signaling logic.

## Setup & Configuration

### System Dependencies (Ubuntu/Debian)

```bash
sudo apt install libjack-jackd2-dev portaudio19-dev
```

### Python Environment

```bash
make venv && source .venv/bin/activate
```

### Environment Variables

Create [`.env`](.env) file or export:

- `OPENAI_API_KEY` — for OpenAI TTS/STT
- `PORCUPINE_ACCESS_KEY` — for Picovoice hotword detection
- `GOOGLE_PROJECT_ID` and `GOOGLE_APPLICATION_CREDENTIALS` — for Google Cloud integrations

### Security Considerations

**⚠️ CRITICAL: Credential and Secret Management**

1. **Never commit credentials**:
   - `.env` file is gitignored by default
   - Never hardcode API keys in source code
   - Never commit Google Cloud service account JSON files
   - Verify `.gitignore` includes: `.env`, `*.pem`, `*.key`, `credentials.json`

2. **Environment variable best practices**:
   - Use `.env` file for local development only
   - Set environment variables directly in production/CI environments
   - Rotate API keys periodically
   - Use separate keys for development vs. production

3. **API key scoping**:
   - OpenAI: Use project-specific keys with minimal required permissions
   - Picovoice: Generate separate access keys per environment
   - Google Cloud: Follow principle of least privilege for service accounts

4. **Voice profile data**:
   - Speaker profiles in `examples/voice_profiles/` contain biometric data
   - Do NOT commit voice profiles to public repositories
   - Implement proper consent mechanisms before collecting voice data
   - Comply with GDPR/privacy regulations for voice data storage

5. **Dependency security**:
   - Run `pip audit` or `safety check` regularly for vulnerability scanning
   - Keep optional ML dependencies (torch, etc.) updated for security patches
   - Pin dependency versions in production deployments

6. **WebRTC security**:
   - Signaling server should use HTTPS/WSS in production
   - Implement proper CORS policies for browser clients
   - Validate and sanitize all peer connection data

### Optional Dependency Groups

Install as needed: `pip install .[openai,google,silero]` or use `make venv` (installs [`requirements.txt`](requirements.txt) only; add extras manually).

See [`pyproject.toml`](pyproject.toml) for all available extras:
- `openai` — OpenAI API integration (STT/TTS)
- `google` — Google Cloud Speech/TTS
- `local-whisper` — Local Whisper transcription
- `silero` — Silero VAD (requires torch)
- `funasr` — FunASR VAD (requires torch)
- `pvcobra` — Picovoice Cobra VAD
- `test` — Coverage tools
- `dev` — Linting and formatting (black, ruff, isort)

## Test Organization & Running

| Test Type | Command | Requires | Purpose |
|-----------|---------|----------|---------|
| **Unit** (offline, default) | `make tests` | None | Fast feedback; mocked APIs |
| **Functional** (offline) | `make functional_tests` | None | Integration of subsystems without real APIs |
| **Online Integration** | `make online_tests` | API keys, network | Real cloud providers, hardware |
| **Single module** | `make test TEST_FILE=tests/path/to/file.py` | Varies | Isolated testing during dev |

**Coverage**: Makefile enforces `--fail-under=90` coverage. HTML report in [`htmlcov`](htmlcov) after `make tests`.

**Test Conventions**:

- Use `unittest` framework (not pytest). Discovery: files in [`tests`](tests) matching `test_*.py`
- Mock external APIs in unit tests
- Name integration tests `integrated_test_*.py` (gated, requires secrets)
- Place functional tests in `tests/functional/` (offline, CI-friendly)
- Use `tests/helpers/audio_utils.py` for generating test audio

## Development Workflows & Patterns

### Code Organization Principles

1. **Keep Public API Stable**: Exports in [`voice_ui/__init__.py`](voice_ui/__init__.py) define the public interface
2. **Factory Registration at Module Load**: Backends self-register when imported
3. **Optional Dependencies**: All cloud integrations and ML backends are optional extras
4. **Interface-First Design**: Define interfaces before implementations

### Linting & Code Style

- **Linting**: `make lint` checks code style before committing
- **Formatter**: Use `black` (in dev extras)
- **Import Sorting**: Use `isort` (in dev extras)
- **Line Length**: Follow PEP 8 (79-99 chars typical)
- **Docstrings**: Use Google-style docstrings for public APIs

### File Naming Conventions

- Unit tests: `test_<module_name>.py`
- Integration tests: `integrated_test_<feature>.py`
- Functional tests: `tests/functional/test_<feature>.py`
- Examples: `##_descriptive_name.py` (numbered) or `##X_descriptive_name_variant.py` (with variant suffix)
- Factories: `<component>_factory.py`
- Interfaces: `i_<component>.py` or `<component>_i.py`

### Creating New Examples

1. Number sequentially (01, 02, 03...) for series
2. Use suffix for variants: `01b_vad_with_hotword.py` (device variant), `02b_speech_detection_webrtc.py` (WebRTC variant)
3. Show realistic end-to-end flows
4. Use descriptive names: `XX_feature_description.py`
5. Include comments explaining setup requirements (API keys, hardware)
6. Reference [`examples/04_voiceui_local.py`](examples/04_voiceui_local.py) as template for full orchestration

### API Stability

- Keep public exports in [`voice_ui/__init__.py`](voice_ui/__init__.py) stable (e.g., `VoiceUI`, `SpeechDetector`, `SpeechEvent` classes)
- Refactor internal modules freely, but coordinate changes to public signatures

## Common Development Tasks

#### Adding a New VAD Backend

1. Create class implementing `IVoiceActivityDetector` in [`voice_ui/voice_activity_detection`](voice_ui/voice_activity_detection)
2. Implement required methods: `process_chunk()`, `reset()`
3. Register in [`voice_ui/voice_activity_detection/__init__.py`](voice_ui/voice_activity_detection/__init__.py):

   ```python
   from .vad_my_backend import MyBackendVAD
   VADFactory.register_vad("my_backend", MyBackendVAD)
   ```

4. Add optional dependencies to [`pyproject.toml`](pyproject.toml):

   ```toml
   my-backend = ["my-backend-package>=1.0.0"]
   ```

5. Create unit tests in `tests/test_vad_my_backend.py`
6. Update documentation

#### Adding a New Transcriber

1. Create class extending `SpeechToTextTranscriber` in [`voice_ui/speech_recognition`](voice_ui/speech_recognition)
2. Implement `transcribe(audio_data, prompt='')` method
3. Register in factory within module's code
4. Follow same dependency and testing pattern as VAD backends

### Adding a New TTS Backend

1. Create class extending `TextToSpeechAudioStreamer` in [`voice_ui/speech_synthesis`](voice_ui/speech_synthesis)
2. Implement `speak(text, voice=None)` and `terminate()` methods
3. Register in factory within module's code
4. Follow same dependency and testing pattern as other backends

## Quick Reference: Key Files

### Core Orchestration

- [`voice_ui/voice_ui.py`](voice_ui/voice_ui.py) — High-level VoiceUI class
- [`voice_ui/speech_detection/speech_detector.py`](voice_ui/speech_detection/speech_detector.py) — VAD + hotword coordinator; emits events
- [`voice_ui/config.py`](voice_ui/config.py) — Configuration dataclass

### Factories

- [`voice_ui/voice_activity_detection/vad_factory.py`](voice_ui/voice_activity_detection/vad_factory.py) — VAD factory + registration
- [`voice_ui/speech_recognition/speech_to_text_transcriber_factory.py`](voice_ui/speech_recognition/speech_to_text_transcriber_factory.py) — Transcriber factory
- [`voice_ui/speech_synthesis/text_to_speech_streamer_factory.py`](voice_ui/speech_synthesis/text_to_speech_streamer_factory.py) — TTS factory

### Audio I/O

- [`voice_ui/audio_io/audio_data.py`](voice_ui/audio_io/audio_data.py) — Audio data structure (immutable)
- [`voice_ui/audio_io/microphone.py`](voice_ui/audio_io/microphone.py) — Device microphone capture
- [`voice_ui/audio_io/virtual_microphone.py`](voice_ui/audio_io/virtual_microphone.py) — Programmatic audio injection; foundation for WebRTC and testing
- [`voice_ui/audio_io/webrtc_remote_microphone.py`](voice_ui/audio_io/webrtc_remote_microphone.py) — WebRTC audio reception
- [`voice_ui/audio_io/player.py`](voice_ui/audio_io/player.py) — Device audio playback
- [`voice_ui/audio_io/virtual_player.py`](voice_ui/audio_io/virtual_player.py) — Queue-based audio sink
- [`voice_ui/audio_io/webrtc_remote_player.py`](voice_ui/audio_io/webrtc_remote_player.py) — WebRTC audio transmission
- [`voice_ui/audio_io/webrtc_signaling_server.py`](voice_ui/audio_io/webrtc_signaling_server.py) — Generic WebRTC signaling (reusable for send/receive)
- [`voice_ui/audio_io/audio_source_factory.py`](voice_ui/audio_io/audio_source_factory.py) — Factory for audio sources
- [`voice_ui/audio_io/audio_sink_factory.py`](voice_ui/audio_io/audio_sink_factory.py) — Factory for audio sinks

### Examples

- [`examples/01_vad_basics.py`](examples/01_vad_basics.py) — Simple VAD with device audio
- [`examples/01b_vad_with_hotword.py`](examples/01b_vad_with_hotword.py) — VAD + hotword detection
- [`examples/02_speech_detection_basics.py`](examples/02_speech_detection_basics.py) — Detection from device microphone
- [`examples/02b_speech_detection_webrtc.py`](examples/02b_speech_detection_webrtc.py) — Detection from WebRTC audio
- [`examples/03_transcription_local.py`](examples/03_transcription_local.py) — Full pipeline with local audio
- [`examples/03b_transcription_webrtc.py`](examples/03b_transcription_webrtc.py) — Full pipeline with WebRTC
- [`examples/04_voiceui_local.py`](examples/04_voiceui_local.py) — Complete real-time system (local audio)
- [`examples/04b_voiceui_webrtc.py`](examples/04b_voiceui_webrtc.py) — Complete real-time system (WebRTC)
- [`examples/05_realtime_api_basics.py`](examples/05_realtime_api_basics.py) — OpenAI Realtime API basics
- [`examples/05b_realtime_api_with_vad.py`](examples/05b_realtime_api_with_vad.py) — OpenAI Realtime API + VAD
- [`examples/webrtc_sender.html`](examples/webrtc_sender.html) — WebRTC sender HTML client

### Testing

- `tests/helpers/audio_utils.py` — Test audio generation utilities
- `tests/functional/` — Offline integration tests
- `integrated_test_*.py` — Online tests (gated, requires API keys)

## Best Practices for AI Agents

### When Reading Code

1. **Start with interfaces and factories** to understand extension points
2. **Check `__init__.py` exports** to identify public API
3. **Read examples** to understand typical usage patterns
4. **Use symbolic tools** (if available) to navigate class hierarchies
5. **Check [`pyproject.toml`](pyproject.toml)** for optional dependencies before suggesting features

### When Writing Code

1. **Implement interfaces, not concrete dependencies** (follow factory pattern)
2. **Add tests** for all new functionality (minimum 90% coverage)
3. **Document environment variables** required by new integrations
4. **Update [`pyproject.toml`](pyproject.toml)** with new optional dependencies
5. **Create examples** for significant new features
6. **Follow existing naming patterns** (factories, tests, examples)

### When Refactoring

1. **Preserve public API** in [`voice_ui/__init__.py`](voice_ui/__init__.py)
2. **Run full test suite** before and after (`make tests`)
3. **Update factories** if interfaces change
4. **Check example compatibility** — examples should continue working
5. **Update documentation** in [`README.md`](README.md) and docstrings

### When Debugging

1. **Check environment variables** are set correctly ([`.env`](.env) file)
2. **Verify optional dependencies** are installed
3. **Run specific test** with `make test TEST_FILE=...`
4. **Enable verbose logging** in examples (most have debug flags)
5. **Test with simple examples first** (01, 02) before complex ones (04, 05)

## Common Pitfalls to Avoid

1. **Don't modify factory registration after module load** — registration is static
2. **Don't assume optional dependencies are available** — check imports with try/except
3. **Don't use pytest** — repository uses unittest framework
4. **Don't create integration tests without gating** — use `integrated_test_*.py` pattern
5. **Don't break audio pipeline immutability** — `AudioData` objects are immutable
6. **Don't skip system dependencies** — PortAudio/JACK are required for audio I/O
7. **Don't batch event handling** — process events individually for responsiveness

## Quick Start for Agents

```bash
# Set up environment
make venv
source .venv/bin/activate

# Run fast offline tests
make tests

# Run a simple example (VAD only, no API key needed)
python examples/01_vad_basics.py

# Run full example (requires OPENAI_API_KEY)
export OPENAI_API_KEY=sk-...
python examples/04_voiceui_local.py

# Test a single module
make test TEST_FILE=tests/test_vad_factory.py
```

## Current Development Focus

From [`TODO.md`](TODO.md) and recent commits:

### Recent Changes

- Reorganized examples with numbered naming scheme and variant suffixes (a/b)
- Refactored `SpeechDetector` for cleaner VAD/hotword separation
- Factory pattern migration from function-based to class-based API complete
- Optional dependency registration happens at module import time
- Web UI preparation in progress

### In Progress

1. **Web UI Integration**:
   - Preparing library for web-based interfaces
   - WebRTC integration for browser-based audio

2. **Hotword Detector Refactoring**:
   - Move `HotwordDetector` to dedicated file
   - Define standardized return types (keyword name, probability array)
   - Implement interface and factory pattern

3. **Voice Profile Manager**:
   - Implement interface and factory
   - Add new speaker identifier backends

4. **Functional Testing Expansion**:
   - Create offline tests for VAD, TTS, STT, and speech detection
   - Ensure CI-friendly without API dependencies

## CI/CD Pipeline

### GitHub Actions Workflow

**Location**: `.github/workflows/ci.yml`

**Triggers**:
- Push to `main` branch
- Pull requests targeting `main`
- Manual workflow dispatch

**Pipeline Steps**:
1. **Environment Setup**:
   - Runs on Ubuntu latest
   - Tests against Python 3.11 (matrix can be expanded)
   - Installs system dependencies: `libjack-jackd2-dev`, `portaudio19-dev`, `sox`

2. **Dependency Installation**:
   - Upgrades pip
   - Installs: `coverage`, `ruff`, `black`
   - Installs requirements from `requirements.txt`

3. **Code Quality Checks**:
   - **Formatting**: `black --check .` (currently permissive with `|| true`)
   - **Linting**: `ruff check . --statistics` (currently permissive)

4. **Testing**:
   - Runs unit tests with `unittest discover`
   - Generates coverage report with `coverage`
   - Enforces 90% minimum coverage (currently permissive with `|| true`)

**⚠️ Current CI Status**:
- All checks are non-blocking (`|| true`) during development phase
- Will be enforced (removing `|| true`) before 1.0 release
- Integration tests requiring API keys do NOT run in CI (by design)

### Local Pre-Commit Checks

Run these before pushing:

```bash
# Formatting
make format         # Auto-format
# Linting
make lint           # Lint check (ruff)

# Testing
make tests          # Unit tests with coverage
make functional_tests  # Offline integration tests

# Optional: Full validation
make format && lint && make tests
```

### Debugging CI Failures

1. **Test failures**:
   - Run locally: `make tests TEST_FILE=tests/path/to/failing_test.py`
   - Check if test requires mocking (no real API calls in CI)
   - Verify system dependencies are available

2. **Coverage failures** (when enforced):
   - Run: `make tests` and open `htmlcov/index.html`
   - Add tests for uncovered branches
   - Minimum required: 90%

3. **Ruff failures** (when enforced):
   - Run: `make lint` locally
   - Fix reported issues
   - Common: line length (79-99 chars), unused imports

4. **Black formatting** (when enforced):
   - Run: `black .` to auto-fix
   - Commit formatted code

### CI Limitations

**What CI tests**:
- ✅ Unit tests with mocked dependencies
- ✅ Functional tests (offline, no real APIs)
- ✅ Code formatting and linting
- ✅ Import resolution

**What CI does NOT test**:
- ❌ Integration tests with real APIs (require secrets)
- ❌ Audio device I/O (no hardware in CI)
- ❌ WebRTC functionality (requires signaling server)
- ❌ Optional ML dependencies (torch/silero/funasr too large)

### Future CI Enhancements

Planned improvements (see [`TODO.md`](TODO.md)):
- [ ] Remove `|| true` to enforce checks
- [ ] Add Python version matrix (3.8, 3.9, 3.10, 3.11, 3.12)
- [ ] Add macOS and Windows runners
- [ ] Cache pip dependencies for faster builds
- [ ] Add separate job for optional dependency groups
- [ ] Integrate security scanning (Dependabot, pip-audit)

## Resources

- **Primary Documentation**: [`README.md`](README.md)
- **Architecture Diagrams**: [`docs/diagram.pu`](docs/diagram.pu) (PlantUML)
- **Configuration Reference**: [`voice_ui/config.py`](voice_ui/config.py) (dataclass with defaults)
- **Task Tracking**: [`TODO.md`](TODO.md) (current development priorities)
- **License**: [`LICENSE`](LICENSE) (MIT License)

---

**For AI Agents**: This repository follows a clean architecture with factory patterns for extensibility. When in doubt, study the existing factories and examples before implementing new features. Always maintain backward compatibility with the public API in [`voice_ui/__init__.py`](voice_ui/__init__.py).

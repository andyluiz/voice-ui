# Technical Context

This file documents the technologies, build tools, and constraints for the voice-ui project.

Languages and frameworks

- Python 3.10+ (project uses typing and modern async patterns)
- Test suite: repository guidance mentions both unittest (per .github/copilot-instructions.md) and pytest in other docs — verify test runner in CI/Makefile (tests are runnable via `make tests`).

Key dependencies

- OpenAI SDK (for Whisper / TTS integrations)
- Google Cloud TTS client (for Google TTS streaming)
- pyaudio or sounddevice for microphone capture in examples
- numpy / torch (when local Whisper or silero models are used)

Project structure

- voice_ui/: main package with modules for VAD, speech recognition, TTS, and audio IO
- examples/: small scripts demonstrating typical usage patterns
- tests/: unit, functional, and integration tests (some require API keys)

Development environment

- Use virtual environments (venv or poetry) to manage dependencies.
- Project includes pyproject.toml for build and dependency metadata.
- Quick setup: make venv && source .venv/bin/activate

Setup & configuration (from repository copilot instructions)

- System deps (Ubuntu/Debian): sudo apt install libjack-jackd2-dev portaudio19-dev
- Environment variables commonly used: OPENAI_API_KEY, PORCUPINE_ACCESS_KEY, GOOGLE_PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS
- Optional extras: pip install .[openai,google,silero]

Constraints and notes

- Local Whisper models and Silero VAD require GPU for reasonable performance in real-time scenarios; CPU-only is supported for batch/offline.
- Some adapters (Picovoice/PORCUPINE) may require platform-native binaries and specific installation steps.
- CI focuses on lightweight integration checks and unit tests; heavy model tests are excluded from CI unless explicitly enabled.

Test runner and conventions

- The repository includes Makefile targets for running tests: `make tests`, `make functional_tests`, and `make online_tests` (online tests require API keys).
- Note: .github/copilot-instructions.md states tests use `unittest` (not pytest) and that test discovery targets files named `test_*.py`. Existing memory-bank files previously referred to pytest — this should be reconciled by checking CI configuration. For now, prefer using the provided Makefile targets which encapsulate the correct runner.

How to add new adapters

1. Implement the adapter following the interface in the corresponding module (e.g., speech_recognition/speech_to_text_transcriber.py)
2. Add a factory entry in the appropriate factory module (e.g., speech_to_text_transcriber_factory)
3. Add an example under examples/ and tests for the new adapter

Notes for agents and contributors

- The repository-level copilot instructions (.github/copilot-instructions.md) were summarized into memory-bank/copilot-instructions.md to make this guidance readily available to AI agents.
- Verify any discrepancies between the copilot instructions and existing docs (e.g., test framework) when making changes that rely on those assumptions.

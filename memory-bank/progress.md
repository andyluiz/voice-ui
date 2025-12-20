# Progress

This changelog-like document captures what works, what's left to build, and known issues.

What works

- Core orchestration for microphone -> VAD -> transcription -> TTS exists and is exercised in examples.
- Multiple VAD adapters implemented and wrapped by a factory.
- Core TTS streamers and queued player are implemented and have tests.

What's left to build

- Increase unit test coverage for edge cases in speech detection and queued player.
- Add contributor guide and onboarding docs.
- Improve CI to allow optional heavy-model integration tests.
- Formalize hotword detection factory and interface; add reference implementations for Picovoice/Porcupine.
- Add configuration class for VoiceUI to simplify example and programmatic usage.

Current status

- Project is in usable state for development and prototyping; some adapters require external setup.

Known issues

- Local Whisper and Silero workflows are slow on CPU-only environments.
- Platform-specific native binaries (e.g., Picovoice) can complicate setup.

Recent progress

- Updated memory bank with foundational documents (product context, system patterns, tech context, active context).
- Added repository-level Copilot instructions summary to memory-bank/copilot-instructions.md to streamline agent onboarding.

# Active Context

This file captures the current work focus, recent changes, and next steps for the voice-ui project.

Current focus

- Improve reliability and test coverage for VAD and TTS components.
- Ensure examples demonstrate real-time audio pipelines with clear instructions.
- Maintain modularity so new adapters can be added with minimal friction.
- Implement and stabilize a clean hotword-detection interface and factory for pluggable hotword backends.
- Provide a clear configuration class for VoiceUI so orchestrations are easier to instantiate and test.

Recent changes

- Added repository-level Copilot instructions and a summarized copy into memory-bank/copilot-instructions.md to help AI agents and contributors onboard quickly.
- Added more documentation and high-level architecture notes to the memory-bank.
- Updated examples to show common microphone and streaming workflows.
- Tests added for integration scenarios (see tests/).

Immediate next steps

- Triage and fix failing tests reported by CI (if any).
- Add or improve unit tests for speech detection and queued player.
- Add a small contributor guide describing how to add adapters and run examples locally.
- Create a hotword detection factory and reference implementations (Picovoice / Porcupine integration notes in .github/copilot-instructions.md).
- Add a configuration class for VoiceUI and migrate example usages to it.

Important decisions

- Keep config centralized in voice_ui/config.py to minimize scattered configuration.
- Use factory/adaptor patterns to decouple third-party SDKs.
- Register adapters/classes at module load to simplify discovery (consistent with the class-based factory registration described in the repo copilot instructions).

Patterns and preferences

- Prefer small, focused functions and clear interfaces over monolithic classes.
- Use async iterators and event callbacks to enable both sync and async usage patterns.

Notes and learnings

- Local model performance varies widely by machine and GPU availability; document expectations clearly in README and examples.
- The repository now documents quick-start setup and environment variables (OPENAI_API_KEY, PORCUPINE_ACCESS_KEY, GOOGLE_PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS) in .github/copilot-instructions.md; mirror these notes in onboarding docs.

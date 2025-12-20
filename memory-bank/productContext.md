# Product Context

This project provides an AI-powered Voice User Interface (VUI) library and tools.

Why this project exists

- To make it easy for developers to add voice interaction to applications without re-implementing low-level audio handling, voice activity detection (VAD), and speech-to-text integrations.
- To provide a modular set of components so users can swap backends (OpenAI, Google, local models, etc.) depending on privacy, latency, or cost requirements.

Problems it solves

- Reduces friction integrating microphone audio, VAD, and speech-to-text in real-time and batched scenarios.
- Supplies a consistent abstraction over heterogeneous speech recognition and synthesis providers.
- Offers ready-made examples for common use cases (microphone hotword detection, streaming transcription, TTS streaming).

User experience goals

- Simple, minimal API to get started quickly (e.g., start a microphone-based VAD -> transcribe -> synthesize).
- Real-time, low-latency audio pipelines where feasible; graceful fallback to queued/batched processing when needed.
- Clear diagnostics and tooling to test different VAD and recognition backends.

Key features

- Voice activity detection adapters (silero, picovoice, funasr, microphone VAD)
- Speech detection and transcription with multiple backends (OpenAI Whisper local, OpenAI Whisper API, Google)
- Text-to-speech streaming and queued players (Google TTS, OpenAI TTS, pass-through streamer)
- Speaker profile manager and speaker embedding utilities (for enrollment / speaker recognition workflows)
- Example scripts demonstrating common workflows and a small test-suite for integration checks

Primary users

- Developers building voice assistants, voice-enabled tools, or research prototypes who need composable building blocks rather than full end-to-end hosted services.

Success criteria

- Clear, well-documented APIs and examples that let new users get a working demo within minutes.
- Modular design that allows swapping components without touching application logic.
- Reliable VAD and transcription integrations across supported backends with test coverage and CI checks.

Notes from copilot instructions

- Repository-level copilot instructions emphasize factory registration at module load, class-based factory API, and examples for onboarding (examples/01..04). Additions to the product context include hotword detection as a first-class component and documented quick-start commands for agents and contributors.

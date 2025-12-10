# System Patterns

This document describes the architecture and common design patterns used across the voice-ui project. It is intended to help contributors understand system boundaries, common integration points, and the expected behavior of components.

High-level architecture

- Audio Input Layer
  - Microphone adapter(s) provide a stream of raw audio frames to the system.
  - There are utilities for both live microphone capture and playback of recorded audio for testing.

- Voice Activity Detection (VAD)
  - A pluggable VAD layer with multiple adapters (silero, picovoice, funasr, microphone VAD).
  - VAD produces segments/notifications used to trigger downstream speech detection and transcription.

- Speech Detection / Transcription
  - Speech detector components turn VAD segments into audio blobs ready for transcription.
  - Transcribers are implemented as interchangeable providers (OpenAI Whisper local, OpenAI API, Google). Use factory and adapter patterns to swap providers.

- Hotword / Wake-word detection
  - Hotword detection is being formalized: add a hotword factory and interface so providers like Picovoice/Porcupine can be registered and swapped at runtime.

- Speaker Profile Management
  - Speaker embedding utilities and a lightweight profile manager allow enrollment and matching for speaker-aware workflows.

- Text-to-Speech (TTS) and Playback
  - Streamed and queued TTS players (Google TTS, OpenAI TTS, pass-through) provide both low-latency streaming and reliable queued playback.
  - Queued player implements producer-consumer behavior to serialize playback and avoid audio overlap.

- Orchestration / High-level API
  - The voice_ui module exposes straightforward orchestration functions that wire together input -> VAD -> transcriber -> TTS.
  - Components are decoupled with events/callbacks or by returning async iterators, enabling both synchronous scripts and asynchronous real-time systems.

Design patterns in use

- Adapter pattern
  - Abstracts third-party backends (VAD, speech-to-text, TTS) behind consistent interfaces so the core logic is backend-agnostic.

- Factory pattern
  - Factory modules create configured instances of transcribers, VADs, and TTS streamers based on configuration settings.

- Strategy pattern
  - Different runtime strategies (e.g., streaming transcription vs. batch) can be selected through configuration.

- Observer / Event-driven callbacks
  - Components emit events (speech_start, speech_end, transcription_result, playback_started, playback_finished) allowing orchestrators or applications to attach handlers.

- Producer-consumer / Queue
  - Queued TTS and audio player use background worker(s) and queues to ensure audio is played reliably and sequentially.

Critical implementation paths

- Real-time microphone pipeline
  - Microphone capture -> VAD adapter -> speech detector -> transcriber (streaming when available) -> synthesize & queued player.
  - Must handle transient noise, short utterances, and ensure low latency.

- Batch / offline processing
  - File or recorded input -> speech detector -> batch transcriber -> post-processing -> TTS (optional) or saved outputs.

- Failover and fallback
  - If a preferred transcriber fails (network, rate limit), factories should be able to swap to a configured fallback (local whisper) without changing application code.

Error handling and observability

- Components should raise descriptive exceptions and provide hooks for logging and metrics.
- Tests and examples include diagnostic utilities to validate VAD sensitivity, transcription latency, and TTS quality.

Configuration and extensibility

- Configuration is centralized in voice_ui/config.py. New adapters should register with the factory functions and follow the project's interface expectations.
- Adding a new backend typically requires implementing the adapter interface, registering it with the factory, and adding an example demonstrating its behavior.

Notes from copilot instructions

- Repository-level instructions emphasize factory registration performed at module load and class-based factory APIs.
- Hotword detection interface and factory are listed as in-progress in the repository guidance and should be prioritized for next steps.

# Copilot Instructions — Summary (from .github/copilot-instructions.md)

This file captures actionable guidance from the repository-level copilot instructions so AI agents (and contributors) can quickly understand the layout, patterns, setup, and current state.

Repository layout (voice_ui package)
- audio_io/: microphone capture and playback (microphone.py, audio_data.py, player.py)
- voice_activity_detection/: VAD adapters + factory (vad_factory.py registers engines like SileroVAD, FunASRVAD, PicoVoiceVAD)
- speech_detection/: speech_detector.py (VAD + hotword + speaker profiling), speaker_profile_manager.py
- speech_recognition/: transcribers + factory (speech_to_text_transcriber_factory.py — registers OpenAIWhisper, LocalWhisper, etc.)
- speech_synthesis/: TTS streamers + factory (text_to_speech_streamer_factory.py — registers OpenAI, Google, PassThrough)
- voice_ui.py: high-level orchestrator wiring VAD -> transcriber -> TTS

Factory pattern (how to extend)
- VADFactory.register_vad(name, class) — register implementations at module load
- TranscriberFactory.register_transcriber(name, class)
- TTSFactory.register_tts(name, class)
- New backend flow: implement adapter class following the interface, register it with the appropriate factory, add examples and tests, and add optional dependencies to pyproject.toml if needed.

Setup & configuration
- System deps (Ubuntu/Debian): sudo apt install libjack-jackd2-dev portaudio19-dev
- Python env: make venv && source .venv/bin/activate
- Environment variables often used: OPENAI_API_KEY, PORCUPINE_ACCESS_KEY, GOOGLE_PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS
- Optional extras: pip install .[openai,google,silero]

Testing & CI
- Test discovery and patterns: unit tests (default, offline), functional tests (offline), integration/online tests (require API keys)
- Test commands (Makefile targets): make tests (unit), make functional_tests, make online_tests
- Note: repository enforces coverage threshold (HTML report in htmlcov/)

Development patterns & conventions
- Adapter, Factory, Strategy patterns used across the codebase
- Observer/event-driven callbacks (speech_start, speech_end, transcription_result, playback_started, playback_finished)
- Queued producer-consumer pattern for serialized TTS playback
- Public API stability: keep exports in voice_ui/__init__.py stable (VoiceUI, SpeechDetector, SpeechEvent)
- Examples are numbered (01..04) and show realistic flows; use example 04 for full orchestration

Quick start for agents / contributors
- make venv
- source .venv/bin/activate
- make tests
- python examples/01_vad_microphone.py (VAD-only example)
- python examples/04_voiceui_real_time_communication.py (full example; requires OPENAI_API_KEY)

Current state & branch notes (from file)
- Branch: reorganize_speech_detector — refactors SpeechDetector with clearer VAD/hotword separation
- Factory classes moved to class-based API; registration performed at module load
- In-progress items (see TODO.md): hotword detection interface + factory, voice profile manager interface, configuration class for VoiceUI

How this was added to memory bank
- This summary preserves the most actionable and agent-oriented parts of .github/copilot-instructions.md: package layout, factory registration conventions, setup and test commands, environment variables, and branch/in-progress notes.

# VoiceUI - AI powered Voice User Interface

Provides an AI powered Voice User Interface.

This package allows for voice activity detection, speech detection and
speech transcription, and speech synthesis using various backends like
OpenAI and Google.

Notes from repository copilot instructions

- The project follows a factory/adaptor architecture for VAD, STT, and TTS backends. New backends should register at module load with the appropriate factory (VADFactory, TranscriberFactory, TTSFactory).
- Examples (01..04) provide quick runnable scripts; example 04 shows a full orchestration of VAD -> STT -> TTS.
- In-progress items: hotword detection interface + factory, voice profile manager improvements, and a configuration class for VoiceUI.

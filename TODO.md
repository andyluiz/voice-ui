# TODO

## Hotword detections

- ~~Move HotwordDetector class to its own file~~
- Define the return type of the `process()` function.
  - Suggestions:
    - the name of the detected keyword
    - a probability array of each keyword
- Implement interface and factory for hotword detectors

## Voice Profile manager

- Implement interface and factory for profile managers
- Implement new speaker identifiers

## Testing

- Create functional tests to check VAD, Speech Synthesis, and Speech Detection and Recognition.

### Online integration tests (gated)

- Purpose: end-to-end tests that exercise cloud APIs, real TTS/STT providers, or hardware (microphone/device I/O).
- Environment: these tests require secrets and/or hardware. Set the following environment variables when running them locally or in a gated CI job:
  - `OPENAI_API_KEY` — OpenAI API key for OpenAI-based transcribers/tts (if used)
  - `PORCUPINE_ACCESS_KEY` — Picovoice Porcupine access key for hotword tests
  - `GOOGLE_PROJECT_ID` and `GOOGLE_APPLICATION_CREDENTIALS` — for Google Cloud integrations
- Run locally (example):

```bash
# activate environment
source .venv/bin/activate

# set required env vars (export or use an env file)
export OPENAI_API_KEY=...
export PORCUPINE_ACCESS_KEY=...
export GOOGLE_PROJECT_ID=...
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/google-creds.json

# run only the integration tests (Makefile helper)
make online_tests
```

## Audio I/O Architecture

- Create an audio sink base class (analogous to `AudioSourceBase`)
  - Design interface for audio output abstractions
  - Refactor `Player` and `WebRTCRemotePlayer` to extend it
  - Create `AudioSinkFactory` for pluggable output backends

## Examples & Documentation

- Revisit all examples:
  - Document each example with setup instructions and prerequisites
  - Improve user experience (progress indicators, better formatting, clearer output)
  - Fully validate each example end-to-end
  - Organize by complexity level (01, 02, 03, 04, 05 series)

## Coverage & Testing

- Increase test coverage from 79% to 90%+
  - Focus on WebRTC modules and optional dependency paths
  - Add integration tests for VAD, TTS, STT, and speech detection
- Reorganize tests into subfolders by module:
  - `tests/voice_activity_detection/`
  - `tests/speech_detection/`
  - `tests/speech_recognition/`
  - `tests/speech_synthesis/`
  - `tests/audio_io/`
  - Keep `tests/helpers/` for shared utilities

## Others

- Create a configuration class for VoiceUI to replace the dictionary.
  - ~~The dictionary is too loose and don't explicitly specify the available settings and their defaults~~
  - Implement a read-config-from-file functionality

- Update diagram
- Create documentation

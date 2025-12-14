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

## Others

- Create a configuration class for VoiceUI to replace the dictionary.
  - ~~The dictionary is too loose and don't explicitly specify the available settings and their defaults~~
  - Implement a read-config-from-file functionality

- Update diagram
- Create documentation

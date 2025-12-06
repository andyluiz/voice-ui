# TODO

## Hotword detections

- Move HotwordDetector class to its own file
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

### Functional tests (new)

- Location: `tests/functional`
- Run locally: create and activate venv, then run `make functional_tests` or:

```bash
source .venv/bin/activate
python -m unittest discover -v tests/functional
```

- Note: These functional tests are designed to be offline and CI-friendly. Online/integration tests that require API keys or microphone hardware remain gated and are run separately (see `make online_tests`).

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

- CI: put online tests behind a dedicated pipeline or job that runs only when secrets are configured and approved (do NOT run by default on forks).

## Others

- Create a configuration class for VoiceUI to replace the dictionary.
  - The dictionary is too loose and don't explicitly specify the available settings and their defaults
  - Implement a read-config-from-file functionality

- Update diagram
- Create documentation

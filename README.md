# Voice UI

Voice UI is a small, modular Python library and examples collection for building voice-driven user interfaces. It provides
abstractions for microphone and audio handling, voice activity detection (VAD), speech-to-text (local and cloud), and
text-to-speech streaming integrations.

Table of contents

- Features
- Project layout
- Quick start
- Setup & dependencies
- Running examples
- Tests & CI
- Development notes
- Contributing

Features

- Microphone + audio buffering helpers in `voice_ui/microphone.py` and `voice_ui/audio_data.py`.
- Multiple VAD and detector implementations under `voice_ui/` (e.g. Silero, Porcupine/Cobra integrations).
- Speech-to-text adapters in `voice_ui/speech_to_text/` and TTS streamers in `voice_ui/speech_synthesis/`.
- Runnable examples demonstrating real-time communication and streaming found in `examples/`.

Project layout (important files)

- `voice_ui/` — main package (core modules, detectors, integrations)
- `examples/` — runnable example scripts (interactive; may require audio hardware or API keys)
- `tests/` — unit and integration tests (uses `unittest`)
- `Makefile` — helper targets for creating the virtualenv, running tests and lint
- `pyproject.toml` — dependency groups (optional extras: `openai`, `google`, `local-whisper`, `silero`, `funasr`)

Quick start (recommended)

1. Create and activate a virtual environment using the Makefile helper:

   ```bash
   make venv
   source .venv/bin/activate
   ```

2. Run the unit test suite (fast, offline):

   ```bash
   make tests
   ```

3. Run an example (example that uses OpenAI TTS — requires `OPENAI_API_KEY`):

   ```bash
   export OPENAI_API_KEY="your_key_here"
   python examples/04_voiceui_real_time_communication.py
   ```

Setup & dependencies

- System (Ubuntu/Debian): audio libraries are required for microphone access and some VAD backends. Install:

   ```bash
   sudo apt install libjack-jackd2-dev portaudio19-dev
   ```

- Python: this project requires Python 3.8+ (see `pyproject.toml`). Install base dependencies:

   ```bash
   pip install -r requirements.txt
   ```

- Optional integrations: `pyproject.toml` lists optional dependency groups. Example: to enable OpenAI `openai` features install:

   ```bash
   pip install .[openai]
   ```

Environment variables

- The examples expect a `.env` or environment variables for cloud integrations. Common variables used in examples:
  - `OPENAI_API_KEY` — OpenAI API key (used by `speech_synthesis/openai_text_to_speech_streamer.py`)
  - `PORCUPINE_ACCESS_KEY` — access key for Porcupine hotword detection
  - `GOOGLE_PROJECT_ID` and `GOOGLE_APPLICATION_CREDENTIALS` — Google Cloud credentials for the `google` extras

Running examples and hardware notes

- Many examples assume a microphone and audio output device (PortAudio/JACK). If you don't have hardware, adapt the example to read from a WAV file and feed samples into the same interfaces used by the examples.
- Example entry points live in `examples/`. Notable scripts:
  - `01_vad_microphone.py` — simple mic-based VAD
  - `03_speech_detection_with_transcription.py` — VAD + transcription flow
  - `04_voiceui_real_time_communication.py` — real-time streaming example (uses TTS/STT integrations)

Tests & CI

- Tests use `unittest` and coverage. The Makefile exposes convenient targets:
  - `make tests` — run full offline test suite with coverage
  - `make online_tests` — run integration tests that require API keys (matches `integrated_test_*.py`)
  - `make test TEST_FILE=tests/...` — run a single test module

Development notes & conventions

- Keep public API in `voice_ui/` stable unless performing a broad refactor.
- Use `unittest` discovery conventions for new tests. Integration tests that require external APIs should be named `integrated_test_*.py` so they can be run with `make online_tests`.
- Linting and formatting: use the `.venv` environment and run `make flake8`. Development tools (black, isort) are listed in `pyproject.toml`.

Code snippets

- Microphone stream (reads raw PCM bytes). Use as a context manager to automatically start/stop:

   ```python
   from voice_ui.audio_io.microphone import MicrophoneStream

   with MicrophoneStream() as mic:
      print('rate:', mic.rate, 'channels:', mic.channels)
      for chunk in mic.generator():
         # `chunk` is raw PCM bytes (mono, 16-bit)
         # process or send to VAD/transcription
         pass
   ```

- Simple `SpeechDetector` consumer. The detector runs in a background thread and calls your callback with events
(e.g. `SpeechStartedEvent`, `SpeechEndedEvent`). Example: save detected speech to WAV.

   ```python
   from voice_ui.speech_detection.speech_detector import SpeechDetector, SpeechEndedEvent
   import wave

   def callback(event):
      if isinstance(event, SpeechEndedEvent):
         ad = event.audio_data
         with wave.open('out.wav', 'wb') as wf:
            wf.setnchannels(ad.channels)
            wf.setsampwidth(ad.sample_size)
            wf.setframerate(ad.rate)
            wf.writeframes(ad.content)

   detector = SpeechDetector(callback=callback)
   detector.start()
   # ... detector runs in background; call `detector.stop()` to stop it
   ```

- OpenAI TTS streamer (requires `OPENAI_API_KEY` in environment). It plays streamed audio via the built-in player thread.

   ```python
   from voice_ui.speech_synthesis.openai_text_to_speech_streamer import OpenAITextToSpeechAudioStreamer

   tts = OpenAITextToSpeechAudioStreamer()
   tts.speak('Hello from Voice UI', voice=OpenAITextToSpeechAudioStreamer.Voice.SHIMMER)
   # When finished, terminate the streamer to clean up threads
   tts.terminate()
   ```

Troubleshooting

- If audio devices are not detected, verify PortAudio/PyAudio are installed and permissions for audio devices are set. On Linux, PulseAudio/JACK configuration may interfere — try running with `aplay`/`arecord` to validate.
- If an optional integration fails (missing package/import), install the corresponding optional extra from `pyproject.toml`.

Contributing

- Open a pull request against the main branch. Include tests for behavioral changes and keep changes small and focused.

License & contact

- Licensed under the MIT License (see `LICENSE`).
- Maintainer: Anderson Silva <andyluiz@yahoo.com>

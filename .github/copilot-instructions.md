<!-- GitHub Copilot / AI agent instructions for the voice-ui repo -->
# Voice UI — Copilot Instructions

This file gives concise, actionable knowledge for AI coding agents to be immediately productive in this repository.

- **Repo layout:** top-level modules and examples
  - `voice_ui/` — main package. Key submodules: `speech_synthesis/`, `speech_detector/`, `microphone.py`, `audio_data.py`, `speech_to_text/`.
  - `examples/` — runnable example scripts (hardware and cloud integrations). Use these to understand runtime flows.
  - `tests/` — unit and integration tests (uses `unittest`, not `pytest`).
  - `docs/` — documentation and doxygen inputs.

- **How to set up & run locally**
  - System deps (Ubuntu): `sudo apt install libjack-jackd2-dev portaudio19-dev` (from `README.md`).
  - Python deps: `pip install -r requirements.txt` or use the Makefile `make venv` to create `.venv` and install.
  - Environment variables: create a `.env` with `OPENAI_API_KEY`, `PORCUPINE_ACCESS_KEY`, `GOOGLE_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS` (see `README.md`).

- **Build / Test / Lint**
  - Tests run with coverage via Makefile targets:
    - `make tests` — runs `coverage run -m unittest discover -v` and generates `htmlcov/`.
    - `make online_tests` — runs integration tests matching `integrated_test_*.py` (requires API keys).
    - Single test: `make test TEST_FILE=tests/path/to/file.py` (Makefile transforms path to a module).
  - Linting: `make flake8` (uses `.venv` bin). Dev extras in `pyproject.toml` include `black`, `flake8`, `isort`.
  - Coverage threshold: Makefile enforces `--fail-under=75` by default.

- **Dependency groups and integrations**
  - `pyproject.toml` defines optional dependency groups: `openai`, `google`, `local-whisper`, `silero`, `funasr`, etc. Use these to determine which integrations require extra packages.
  - Example: `voice_ui/speech_synthesis/openai_text_to_speech_streamer.py` uses the `openai` optional API; only run related examples when `openai` deps and `OPENAI_API_KEY` exist.

- **Runtime patterns & conventions**
  - Examples are often interactive and assume microphone/audio hardware (PortAudio/JACK). Prefer running in a machine with audio devices or adapt examples to file-based inputs.
  - Tests are organized for offline unit tests and separate online/integration tests. Online tests require real API keys and are explicitly executed with `make online_tests`.
  - Use `unittest` discovery conventions — tests are discovered under `tests/` and integration tests use the `integrated_test_*.py` pattern.

- **What to modify vs preserve**
  - Keep public API surfaces in `voice_ui/` stable unless refactoring across the package.
  - Avoid changing CI / coverage thresholds without coordinating with maintainers.

- **Where to look for examples of important patterns**
  - Real-time streaming + VAD: `examples/04_voiceui_real_time_communication.py` and `voice_ui/vad_*` implementations.
  - Microphone and audio plumbing: `voice_ui/microphone.py`, `voice_ui/audio_data.py`.
  - Speech-to-text & TTS integrations: files inside `voice_ui/speech_to_text/` and `voice_ui/speech_synthesis/` (see `openai_text_to_speech_streamer.py`).

- **Merging guidance**
  - If an existing `.github/copilot-instructions.md` exists, preserve any manually curated sections. When adding new content, append under a single new header and avoid removing existing human-written guidance.

- **Quick examples for agents**
  - Run the unit test suite locally (fast, offline):
    - `make venv && source .venv/bin/activate && make tests`
  - Run a single integration example that uses OpenAI TTS (requires env key):
    - `export OPENAI_API_KEY=... && python examples/04_voiceui_real_time_communication.py`

If anything important is missing from these instructions (tooling, CI, or uncommon repo conventions), tell me which area to inspect and I'll update this file.

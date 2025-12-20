# Voice UI Tools

Utility scripts for the Voice UI project.

## `generate_hotword_resources.py`

CLI tool to generate hotword resource files for testing. Supports two modes:

1. **TTS Mode**: Synthesize phrases using OpenAI or Google Cloud Text-to-Speech
2. **Microphone Mode**: Record audio from your microphone

Output files are automatically converted to 16 kHz mono 16-bit PCM WAV format (Porcupine-compatible).

### Usage

#### List available TTS engines

```bash
python tools/generate_hotword_resources.py --list-engines
```

#### Generate using OpenAI TTS (direct API)

```bash
export OPENAI_API_KEY=sk-...
python tools/generate_hotword_resources.py \
  --mode tts \
  --tts-engine openai-tts-raw \
  --filenames hotword_alexa_keyword.wav=alexa \
  --filenames hotword_computer_keyword.wav=computer \
  --filenames hotword_no_keyword.wav="hello world"
```

#### Generate using Google Cloud TTS

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
python tools/generate_hotword_resources.py \
  --mode tts \
  --tts-engine google \
  --tts-params language_code=en-US \
  --filenames hotword_computer_keyword.wav=computer
```

#### Record from microphone

```bash
python tools/generate_hotword_resources.py \
  --mode record \
  --duration 2.0 \
  --filenames hotword_recorded_keyword.wav=computer
```

When running in record mode, the tool will:
1. Prompt you to press Enter to start
2. Record for the specified duration
3. Save the file automatically

To use a specific microphone device (if you have multiple):

```bash
python tools/generate_hotword_resources.py \
  --mode record \
  --device-index 1 \
  --duration 2.0 \
  --filenames hotword_recorded_keyword.wav=computer
```

#### Dry-run mode

See what would be generated without actually creating files:

```bash
python tools/generate_hotword_resources.py \
  --mode tts \
  --dry-run \
  --filenames hotword_alexa_keyword.wav=alexa
```

#### Overwrite existing files

By default, the tool skips files that already exist. Use `--force` to overwrite:

```bash
python tools/generate_hotword_resources.py \
  --mode tts \
  --force \
  --filenames hotword_alexa_keyword.wav=alexa
```

#### Verbose logging

Enable debug output:

```bash
python tools/generate_hotword_resources.py \
  --mode tts \
  --verbose \
  --filenames hotword_alexa_keyword.wav=alexa
```

### Output directory

Files are saved to `tests/resources/hotword/` by default. Override with `--output-dir`:

```bash
python tools/generate_hotword_resources.py \
  --mode tts \
  --output-dir /path/to/custom/dir \
  --filenames hotword_alexa_keyword.wav=alexa
```

### Environment variables

- `OPENAI_API_KEY` — Required for OpenAI TTS (`openai-tts-raw` engine)
- `GOOGLE_APPLICATION_CREDENTIALS` — Path to Google Cloud service account JSON (for Google TTS)

Load from `.env` automatically with `python-dotenv`.

### Dependencies

**Core:**
- `python-dotenv` — Load environment variables
- `requests` — HTTP client for OpenAI API

**TTS Modes:**
- `requests` — For OpenAI TTS API

**Microphone Recording:**
- `pvrecorder` — Picovoice microphone recorder

**Audio Processing:**
- Built-in `wave` and `audioop` modules

### Integration with tests

Generated files are named to match expectations in [tests/integrated_test_hotword_detector.py](../tests/integrated_test_hotword_detector.py):

- `hotword_alexa_keyword.wav` — Should detect "alexa" keyword
- `hotword_computer_keyword.wav` — Should detect "computer" keyword
- `hotword_jarvis_keyword.wav` — Should detect "jarvis" keyword
- `hotword_hey_google_keyword.wav` — Should detect "hey google" keyword
- `hotword_no_keyword.wav` — Should NOT detect a keyword

Run the hotword detector test after generating resources:

```bash
python -m unittest tests/integrated_test_hotword_detector.py -v
```

To enforce that detections match expectations, set the environment variable:

```bash
export HOTWORD_TEST_ENFORCE_DETECTION=1
python -m unittest tests/integrated_test_hotword_detector.py -v
```

### Troubleshooting

**"OPENAI_API_KEY not set"**
Set your OpenAI API key in the environment or a `.env` file in the repo root:
```bash
echo "OPENAI_API_KEY=sk-..." > .env
```

**"pvrecorder library required"**
Install the Picovoice recorder:
```bash
pip install pvrecorder
```

**"Audio format error"**
The tool automatically converts audio to 16 kHz mono 16-bit PCM. If conversion fails, check that:
- The TTS engine returns valid WAV format
- Your microphone is compatible with 16-bit PCM recording

**Microphone not found**
List available devices (requires `pvrecorder`):
```bash
python -c "import pvrecorder; print(pvrecorder.get_available_devices())"
```

Then pass the device index with `--device-index N`.

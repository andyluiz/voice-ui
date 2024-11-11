# Voice UI

## Setup

Install *portaudio* and *libjack*

```bash
sudo apt install libjack-jackd2-dev portaudio19-dev
```

Install python requirements

```bash
pip install -r requirements.txt
```

Create a .env file with the following content:

```bash
OPENAI_API_KEY = <openai_key>
PORCUPINE_ACCESS_KEY = <porcupine_key>
GOOGLE_PROJECT_ID = <google_project_id>
GOOGLE_APPLICATION_CREDENTIALS = <google_credentials_path>
```

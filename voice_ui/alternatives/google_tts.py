import argparse
import os
import sys
import tempfile

from google.cloud import texttospeech

# Include path to allow for local execution
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../'))

import config  # noqa: F401
from utils import player


def init():
    player.init()


def quit():
    player.quit()


def synthesize_speech(text=None, ssml=None,
                      language="en-US",
                      ssml_gender=texttospeech.SsmlVoiceGender.FEMALE, voice_name=None):
    """Synthesizes speech from the input file of text."""
    # Instantiates a client
    client = texttospeech.TextToSpeechClient()

    # Set the text input to be synthesized
    input_text = texttospeech.SynthesisInput(text=text, ssml=ssml)

    # Build the voice request, select the language code ("en-US") and the ssml voice gender
    voice = texttospeech.VoiceSelectionParams(
        name=voice_name,
        language_code=language,
        ssml_gender=ssml_gender
    )

    # Select the type of audio file you want return
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    # Perform the text-to-speech request on the text input with the selected
    # voice parameters and audio file type
    response = client.synthesize_speech(
        request={
            "input": input_text,
            "voice": voice,
            "audio_config": audio_config
        }
    )

    return response.audio_content


def list_voices(language):
    # Instantiates a client
    client = texttospeech.TextToSpeechClient()

    result = client.list_voices(language_code=language)

    return [
        {
            'language_codes': [code for code in voice.language_codes],
            'name': voice.name,
            'natural_sample_rate_hertz': voice.natural_sample_rate_hertz,
            'ssml_gender': voice.ssml_gender.name,
        }
        for voice in result.voices
    ]


def say(text=None, ssml=None,
        language="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE, voice_name=None):
    """Synthesizes speech from the input file of text."""

    audio_content = synthesize_speech(
        text=text,
        ssml=ssml,
        language=language,
        ssml_gender=ssml_gender,
        voice_name=voice_name
    )

    # Create a temporary file in the default temporary directory
    temp_file = tempfile.NamedTemporaryFile(prefix='gpt3_', suffix='.mp3', delete=False)

    # The response's audio_content is binary.
    temp_file.write(audio_content)

    # Close the file
    temp_file.close()

    # Play the temporary file
    player.play_file(temp_file.name)

    # Close the file and delete it
    os.unlink(temp_file.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Text-To-Speech")
    parser.add_argument('-s', '--ssml', help='Enable Speech Synthesis Markup Language (SSML) mode', action='store_true')
    parser.add_argument('-l', '--language', help='Language of text', default='en-US')
    parser.add_argument('-g', '--gender', help='Gender of the voice to use', choices=['MALE', 'FEMALE', 'NEUTRAL'])
    parser.add_argument('-v', '--voice', help='Name of the voice to use')
    parser.add_argument('--list-voices', help='List available voices for the specified language', action='store_true')

    parser.add_argument('input',
                        nargs='?', type=argparse.FileType('r'), default=sys.stdin,
                        help='File containing the text to be converted to speech or "-" to read from stdin')

    args = parser.parse_args()

    if args.list_voices:
        print(list_voices(language=args.language))
        exit(0)

    init()

    ssml_gender = None  # texttospeech.SsmlVoiceGender.SSML_VOICE_GENDER_UNSPECIFIED
    if args.gender == 'MALE':
        ssml_gender = texttospeech.SsmlVoiceGender.MALE
    elif args.gender == 'FEMALE':
        ssml_gender = texttospeech.SsmlVoiceGender.FEMALE
    elif args.gender == 'NEUTRAL':
        ssml_gender = texttospeech.SsmlVoiceGender.NEUTRAL

    params = {
        'language': args.language,
        'ssml_gender': ssml_gender,
        'voice_name': args.voice
    }

    text = args.input.read().strip()

    if args.ssml:
        params['ssml'] = text
    else:
        params['text'] = text

    say(**params)

    exit(0)

    # say(text="Hello World! This is a test of the text-to-speech API.")
    # say(ssml="<speak><emphasis level=\"strong\">Olá mundo!</emphasis> Isso é um teste da <say-as interpret-as=\"characters\">API</say-as> de conversão de fala para texto do Google.</speak>", language="pt-BR")
    say(ssml="""
<speak>The Haversine formula is used to calculate the distance between two points on a sphere. The formula is as follows:

d = 2 * r * sin (θ/2)

where d is the distance, r is the radius of the sphere, and θ is the angle between the two points.

To use the formula, we first need to calculate the latitude and longitude of both Eindhoven and Oslo.

<s>Eindhoven: 51.4500° N, 5.4750° E</s>
<s>Oslo: 59.9500° N, 10.7500° E</s>

Then, we plug these values into the formula to get:

d = 2 * 6371 * sin ((59.95 - 51.45)/2)</speak>
""")

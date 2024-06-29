from __future__ import division

import logging
import os

import colorama
from google.cloud import speech
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech
from google.protobuf.duration_pb2 import Duration


def google_speech_v2_recognize(
    stream,
    project_id: str = None,
    language_codes: list[str] = ['en-US'],
    prefix: str = '',
    speech_start_timeout: int = 10,
    speech_end_timeout: int = 3,
    recognition_model: str = 'latest_long'
):
    """
    Recognizes speech from an audio stream using Google Speech v2 API.

    Args:
        stream (AudioStream): The audio stream to recognize.
        project_id (str): The Google Cloud project ID.
        language_codes (list[str]): A list of language codes to recognize.
        prefix (str): A string to print before the recognized text.
        speech_start_timeout (int): The timeout for speech start in seconds.
        speech_end_timeout (int): The timeout for speech end in seconds.
        recognition_model (str): The model to use for recognition.

    Returns:
        cloud_speech.StreamingRecognizeResponse: The response from the API.
    """
    if project_id is None:
        project_id = os.environ['GOOGLE_PROJECT_ID']

    # diarization_config = cloud_speech.SpeakerDiarizationConfig(
    #     min_speaker_count=None,
    #     max_speaker_count=None,
    # )

    recognition_features = cloud_speech.RecognitionFeatures(
        enable_automatic_punctuation=True,
        # diarization_config=diarization_config,
    )

    recognition_config = cloud_speech.RecognitionConfig(
        explicit_decoding_config=cloud_speech.ExplicitDecodingConfig(
            encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=stream._rate,
            audio_channel_count=stream._channels,
        ),
        features=recognition_features,
        language_codes=language_codes,
        model=recognition_model,
    )

    streaming_features = cloud_speech.StreamingRecognitionFeatures(
        interim_results=True,
        enable_voice_activity_events=True,
        voice_activity_timeout=cloud_speech.StreamingRecognitionFeatures.VoiceActivityTimeout(
            speech_start_timeout=Duration(seconds=speech_start_timeout),
            speech_end_timeout=Duration(seconds=speech_end_timeout),
        ),
    )

    streaming_config = cloud_speech.StreamingRecognitionConfig(
        config=recognition_config,
        streaming_features=streaming_features,
    )

    config_request = cloud_speech.StreamingRecognizeRequest(
        recognizer=f"projects/{project_id}/locations/global/recognizers/_",
        streaming_config=streaming_config,
    )

    stream.resume()
    audio_generator = stream.generator()

    audio_requests = (
        cloud_speech.StreamingRecognizeRequest(audio=content) for content in audio_generator
    )

    print(prefix, end='', flush=True)

    def requests(rec_config: cloud_speech.RecognitionConfig, audio: list) -> list:
        yield rec_config
        yield from audio

    # Transcribes the audio into text
    client = SpeechClient()

    responses_iterator = client.streaming_recognize(
        requests=requests(config_request, audio_requests)
    )

    transcripts = []

    for response in responses_iterator:
        logging.debug(f"Speech-to-Text response: {response}")

        if not response.results:
            continue

        # The `results` list is consecutive. For streaming, we only care about
        # the first result being considered, since once it's `is_final`, it
        # moves on to considering the next utterance.
        result = response.results[0]
        if not result.alternatives:
            continue

        # Display the transcription of the top alternative.
        transcript = result.alternatives[0].transcript

        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.
        #
        # If the previous result was longer than this one, we need to print
        # some extra spaces to overwrite the previous result

        if not result.is_final:
            colorama.ansi.clear_line(mode=0)
            print(prefix + transcript, end="\r", flush=True)
            colorama.ansi.Cursor.FORWARD(len([s for s in prefix if s.isprintable()]))

        else:
            # stream.pause()

            # print(prefix + transcript)

            result = {
                'text': transcript,
                'confidence': result.alternatives[0].confidence,
                'language_code': result.language_code,
                'total_billed_time': response.metadata.total_billed_duration.seconds,
            }
            transcripts.append(result)
            logging.debug(f"Speech transcript: {result}")

            # return result

    stream.pause()

    result = None
    if len(transcripts) > 0:
        result = {
            'text': ' '.join([t['text'].strip() for t in transcripts]),
            # 'confidence': 0,
            'language_code': ','.join(list(set([t['language_code'].strip() for t in transcripts]))),
            'total_billed_time': sum([t['total_billed_time'] for t in transcripts]),
        }
        print(prefix + result['text'])

    logging.debug(f"Speech transcript: {result}")
    return result


def listen(
    stream,
    language_codes=[],
    **kwargs
):
    language_codes = list(set(language_codes + ["en-US"]))

    return google_speech_v2_recognize(
        project_id=os.environ['GOOGLE_PROJECT_ID'],
        stream=stream,
        language_codes=language_codes,
        **kwargs
    )


def transcribe_file(
    speech_file: str,
    language_code: str = "en-US",
    alternative_language_codes=None
):
    """Transcribe the given audio file."""
    import sox

    tfm = sox.Transformer()
    tfm.set_output_format(file_type='wav', rate=16000)
    content = tfm.build_array(input_filepath=speech_file)

    # with open('audio.wav', "rb") as audio_file:
    #     content = audio_file.read()
    audio = speech.RecognitionAudio(content=content.tobytes())

    # diarization_config = speech.SpeakerDiarizationConfig(
    #     enable_speaker_diarization=True,
    #     min_speaker_count=None,
    #     max_speaker_count=None,
    # )

    client = speech.SpeechClient()
    rec_config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code=language_code,
        alternative_language_codes=alternative_language_codes,
        enable_automatic_punctuation=True,  # Enable automatic punctuation
        # diarization_config=diarization_config,
    )

    response = client.recognize(config=rec_config, audio=audio)

    # Each result is for a consecutive portion of the audio. Iterate through
    # them to get the transcripts for the entire audio file.
    transcripts = []
    for result in response.results:
        # The first alternative is the most likely one for this portion.
        transcripts.append(result.alternatives[0].transcript.strip())

    return '\n'.join(transcripts)


# if __name__ == "__main__":
#     def setup_logging(log_level: int):
#         import tempfile

#         # Configure the logger
#         # Get the base filename of the current script without extension
#         script_filename = os.path.splitext(os.path.basename(__file__))[0]
#         log_filename = os.path.join(tempfile.gettempdir(),
#                                     f'{script_filename}.log')

#         logging.basicConfig(
#             level=log_level,
#             format="%(asctime)s [%(levelname)s] %(message)s",
#             handlers=[
#                 logging.StreamHandler(),
#                 logging.FileHandler(log_filename),
#             ],
#         )

#     setup_logging(log_level=logging.DEBUG)

#     transcript = transcribe_file('artemis.wav', alternative_language_codes=['pt-BR'])
#     print(transcript)

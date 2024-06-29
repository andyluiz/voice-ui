import unittest
from unittest.mock import MagicMock, patch

import voice_ui.alternatives.google_speech_recognition as sr
from google.cloud import speech
from google.cloud.speech_v2.services.speech.client import SpeechClient
from google.cloud.speech_v2.types import cloud_speech
from google.protobuf.duration_pb2 import Duration


# Create a mock audio stream object
class MockAudioStream:
    def __init__(self):
        self._rate = 16000
        self._channels = 1

    def resume(self):
        pass

    def pause(self):
        pass

    def generator(self):
        yield b'audio_data'


def mock_SpeechClient_init(*args, **kwargs):
    pass


class TestGoogleSpeechV2Recognize(unittest.TestCase):
    def setUp(self):
        # Create a mock stream object
        self.mock_stream = MagicMock(
            _rate=16000,
            _channels=1,
            generator=MagicMock(return_value=['audio_data']),
        )

    @patch.object(SpeechClient, '__init__', mock_SpeechClient_init)
    @patch('google.cloud.speech_v2.types.cloud_speech.StreamingRecognizeRequest')
    @patch('google.cloud.speech_v2.types.cloud_speech.StreamingRecognitionConfig')
    @patch('google.cloud.speech_v2.types.cloud_speech.StreamingRecognitionFeatures')
    @patch('google.cloud.speech_v2.types.cloud_speech.RecognitionConfig')
    @patch('google.cloud.speech_v2.types.cloud_speech.RecognitionFeatures')
    @patch('google.cloud.speech_v2.SpeechClient.streaming_recognize')
    def test_google_speech_v2_recognize(
        self,
        mock_streaming_recognize,
        mock_RecognitionFeatures,
        mock_RecognitionConfig,
        mock_StreamingRecognitionFeatures,
        mock_StreamingRecognitionConfig,
        mock_StreamingRecognizeRequest
    ):
        mock_RecognitionFeatures.return_value = MagicMock()
        mock_RecognitionConfig.return_value = MagicMock()
        mock_StreamingRecognitionFeatures.return_value = MagicMock()
        mock_StreamingRecognitionConfig.return_value = MagicMock()
        mock_StreamingRecognizeRequest.return_value = MagicMock()

        mock_response = MagicMock(
            results=[
                MagicMock(
                    is_final=True,
                    alternatives=[
                        MagicMock(transcript='test_transcript', confidence=0.9)
                    ],
                    language_code='en-US'
                )
            ],
            metadata=MagicMock(total_billed_duration=MagicMock(seconds=10)),
        )

        mock_streaming_recognize.return_value = [
            mock_response
        ]

        result = sr.google_speech_v2_recognize(
            stream=self.mock_stream,
            project_id='my_project_id',
            language_codes=['en-US'],
            prefix='',
            speech_start_timeout=10,
            speech_end_timeout=5,
            recognition_model='long'
        )

        expected_result = {
            'text': 'test_transcript',
            # 'confidence': 0.9,
            'language_code': 'en-US',
            'total_billed_time': 10,
        }

        mock_RecognitionFeatures.assert_called_once_with(
            enable_automatic_punctuation=True,
            # diarization_config=diarization_config,
        )
        mock_RecognitionConfig.assert_called_once_with(
            explicit_decoding_config=cloud_speech.ExplicitDecodingConfig(
                encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.mock_stream._rate,
                audio_channel_count=self.mock_stream._channels,
            ),
            features=mock_RecognitionFeatures.return_value,
            language_codes=['en-US'],
            model='long',
        )
        mock_StreamingRecognitionFeatures.assert_called_once_with(
            interim_results=True,
            enable_voice_activity_events=True,
            voice_activity_timeout=cloud_speech.StreamingRecognitionFeatures.VoiceActivityTimeout(
                speech_start_timeout=Duration(seconds=10),
                speech_end_timeout=Duration(seconds=5),
            ),
        )
        mock_StreamingRecognitionConfig.assert_called_once_with(
            config=mock_RecognitionConfig.return_value,
            streaming_features=mock_StreamingRecognitionFeatures.return_value,
        )
        mock_StreamingRecognizeRequest.assert_called_once_with(
            recognizer="projects/my_project_id/locations/global/recognizers/_",
            streaming_config=mock_StreamingRecognitionConfig.return_value
        )

        self.mock_stream.resume.assert_called_once()
        mock_streaming_recognize.assert_called_once()
        self.mock_stream.pause.assert_called_once()
        self.assertEqual(result, expected_result)

    @patch.object(SpeechClient, '__init__', mock_SpeechClient_init)
    @patch('os.environ', {'GOOGLE_PROJECT_ID': 'test_project_id'})
    @patch('google.cloud.speech_v2.SpeechClient.streaming_recognize')
    def test_google_speech_v2_recognize_no_return(self, mock_streaming_recognize):
        mock_streaming_recognize.return_value = [
            MagicMock(results=None),
            MagicMock(results=[]),
            MagicMock(results=[MagicMock(alternatives=None)]),
            MagicMock(results=[MagicMock(alternatives=[])]),
            MagicMock(results=[MagicMock(is_final=False, alternatives=[MagicMock(transcript='not stable')])]),
        ]

        result = sr.google_speech_v2_recognize(
            stream=self.mock_stream,
        )

        self.mock_stream.resume.assert_called_once()
        self.mock_stream.pause.assert_called_once()
        self.assertIsNone(result)


class ListenTestCase(unittest.TestCase):
    @patch('os.environ', {'GOOGLE_PROJECT_ID': 'TEST_ID'})
    @patch('voice_ui.alternatives.google_speech_recognition.google_speech_v2_recognize')
    def test_listen_with_language_code(self, mock_google_speech_v2_recognize):
        stream = MockAudioStream()
        language_codes = ["en-US"]

        # Call the function under test
        sr.listen(stream, language_codes=language_codes)

        # Assert that google_speech_v2_recognize was called with the correct arguments
        mock_google_speech_v2_recognize.assert_called_once_with(
            project_id='TEST_ID',
            stream=stream,
            language_codes=language_codes,
        )

    @patch('os.environ', {'GOOGLE_PROJECT_ID': 'TEST_ID'})
    @patch('voice_ui.alternatives.google_speech_recognition.google_speech_v2_recognize')
    def test_listen_with_alternative_language_codes(self, mock_google_speech_v2_recognize):
        stream = MockAudioStream()
        language_codes = ["fr-FR", "es-ES"]

        # Call the function under test
        sr.listen(stream, language_codes=language_codes)

        # Assert that google_speech_v2_recognize was called with the correct arguments
        expected_language_codes = list(set(language_codes + ['en-US']))
        mock_google_speech_v2_recognize.assert_called_once_with(
            project_id='TEST_ID',
            stream=stream,
            language_codes=expected_language_codes,
        )


class TestTranscribeFile(unittest.TestCase):

    @patch.object(speech.SpeechClient, '__init__', mock_SpeechClient_init)
    @patch('sox.Transformer')
    @patch('google.cloud.speech_v1.SpeechClient.recognize')
    def test_transcribe_file(self, mock_SpeechClient, mock_Transformer):
        # Create a mock transformer object
        mock_content = MagicMock()
        mock_content.tobytes.return_value = b'audio_data'

        mock_transformer = MagicMock()
        mock_transformer.build_array.return_value = mock_content
        mock_Transformer.return_value = mock_transformer

        # Mock RecognitionResponse
        mock_result = MagicMock()
        mock_result.alternatives = [MagicMock(transcript='test_transcript')]

        mock_response = MagicMock()
        mock_response.results = [mock_result]
        mock_SpeechClient.return_value = mock_response

        result = sr.transcribe_file(speech_file='test_speech_file')

        expected_result = 'test_transcript'

        mock_SpeechClient.assert_called_once()

        self.assertEqual(result, expected_result)


if __name__ == '__main__':
    unittest.main()

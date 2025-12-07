import unittest
from datetime import datetime
from pathlib import Path
from queue import Empty
from threading import Thread
from unittest.mock import MagicMock, call, patch

from voice_ui import (
    PartialTranscriptionEvent,
    TranscriptionEvent,
    VoiceUI,
    VoiceUIConfig,
    WaitingForHotwordEvent,
)
from voice_ui.speech_detection.speech_detector import (
    MetaDataEvent,
    PartialSpeechEndedEvent,
    SpeechDetector,
    SpeechEndedEvent,
    SpeechStartedEvent,
)


# Mock imports from the module where VoiceUI is defined
class TestVoiceUI(unittest.TestCase):

    @patch('os.environ', {'PORCUPINE_ACCESS_KEY': '1234', 'OPENAI_API_KEY': '1234'})
    def setUp(self):
        self.mock_speech_callback = MagicMock()
        self.mock_config = VoiceUIConfig(
            voice_name='test_voice',
            voice_profiles_dir=Path('/tmp/voice_profiles'),
        )

        with (
            patch.object(SpeechDetector, '__new__', spec=SpeechDetector),
            patch('voice_ui.voice_ui.TTSFactory.create') as mock_create_tts_streamer,
            patch('voice_ui.voice_ui.TranscriberFactory.create') as mock_transcriber_factory,
        ):
            self.voice_ui = VoiceUI(speech_callback=self.mock_speech_callback, config=self.mock_config)

            mock_create_tts_streamer.assert_called_once()
            mock_transcriber_factory.assert_called_once()

    def test_initialization(self):
        self.assertTrue(self.voice_ui._terminated)
        self.assertEqual(self.voice_ui._config, self.mock_config)

    @patch.object(Thread, 'start')
    def test_start(self, mock_thread_start):
        self.voice_ui._speech_detector.start.assert_not_called()

        self.voice_ui.start()

        self.assertFalse(self.voice_ui._terminated)

        self.voice_ui._speech_detector.start.assert_called_once()

        mock_thread_start.assert_has_calls([call(), call()])

    @patch.object(Thread, 'start')
    @patch.object(Thread, 'join')
    def test_terminate(self, mock_thread_join, mock_thread_start):
        self.voice_ui.start()
        self.voice_ui.terminate(timeout=1)

        self.assertTrue(self.voice_ui._terminated)

        self.voice_ui._speech_detector.stop.assert_called_once()

        self.assertEqual(mock_thread_join.call_count, 2)

    @patch('voice_ui.voice_ui.datetime')
    @patch.object(Thread, 'start')
    @patch('voice_ui.voice_ui.logging.error')
    @patch('voice_ui.speech_detection.speech_detector.uuid4', return_value='0')
    def test_listener_queue_empty(self, mock_uuid4, mock_logging_error, mock_thread_start, mock_datetime):
        mock_datetime.now = MagicMock(
            side_effect=[
                datetime(2022, 1, 1, 0, 0, 0, 0),
                datetime(2022, 1, 1, 0, 0, 40, 0),
                datetime(2022, 1, 1, 0, 0, 50, 0),
            ]
        )
        self.voice_ui._tts_streamer.is_speaking = MagicMock(return_value=False)
        self.voice_ui._terminated = False
        self.voice_ui._config = VoiceUIConfig(
            voice_name='test_voice',
            voice_profiles_dir=Path('/tmp/voice_profiles'),
            hotword_inactivity_timeout=30,
        )

        def spech_input_get_side_effect(timeout):
            self.voice_ui._terminated = True
            raise Empty

        self.voice_ui._speech_events.get = MagicMock(side_effect=spech_input_get_side_effect)

        self.voice_ui._speech_event_handler()

        mock_datetime.now.assert_has_calls([call(), call()])
        self.voice_ui._speech_detector.set_detection_mode.assert_called_once_with(SpeechDetector.DetectionMode.HOTWORD)

        mock_uuid4.assert_called_once()

        self.mock_speech_callback.assert_has_calls([
            call(event=WaitingForHotwordEvent()),
        ])

    @patch('voice_ui.voice_ui.datetime')
    @patch.object(Thread, 'start')
    @patch('voice_ui.voice_ui.logging.error')
    @patch('voice_ui.speech_detection.speech_detector.uuid4', return_value='0')
    def test_listener(self, mock_uuid4, mock_logging_error, mock_thread_start, mock_datetime):
        mock_datetime.now = MagicMock(
            return_value=datetime(2022, 1, 1, 0, 0, 0, 0)
        )

        self.voice_ui._terminated = False

        inputs = [
            SpeechStartedEvent(),
            MetaDataEvent(audio_data=None),
            PartialSpeechEndedEvent(audio_data=None, metadata={'speaker': {'name': 'John Doe'}}),
            PartialSpeechEndedEvent(audio_data='audio data 2', metadata={'speaker': {'name': 'John Doe'}}),
            SpeechEndedEvent(audio_data='audio data 3', metadata=None),
        ]

        def speech_input_get_side_effect(timeout):
            value = inputs.pop(0)
            if len(inputs) == 0:
                self.voice_ui._terminated = True

            return value

        self.voice_ui._speech_events.get = MagicMock(side_effect=speech_input_get_side_effect)

        self.voice_ui._audio_transcriber.transcribe = MagicMock(
            side_effect=[
                'transcribed partial text',
                'transcribed final text',
            ]
        )

        self.voice_ui._speech_event_handler()

        self.voice_ui._audio_transcriber.transcribe.assert_has_calls([
            call(audio_data='audio data 2', prompt=''),
            call(audio_data='audio data 3', prompt='transcribed partial text'),
        ])

        self.voice_ui._speech_events.get.assert_has_calls([
            call(timeout=1),
            call(timeout=1),
            call(timeout=1),
            call(timeout=1),
            call(timeout=1)
        ])

        self.voice_ui._speech_detector.stop.assert_not_called()
        self.voice_ui._speech_detector.detect_hot_keyword.assert_not_called()
        self.voice_ui._speech_detector.start.assert_not_called()

        # mock_logging_error.assert_not_called()

        mock_uuid4.assert_has_calls([
            call(),
            call()
        ])

        self.mock_speech_callback.assert_has_calls([
            call(event=SpeechStartedEvent()),
            call(event=PartialSpeechEndedEvent(audio_data=None, metadata={'speaker': {'name': 'John Doe'}})),
            call(event=PartialSpeechEndedEvent(audio_data='audio data 2', metadata={'speaker': {'name': 'John Doe'}})),
            call(event=PartialTranscriptionEvent(text='transcribed partial text', speaker='John Doe', speech_id='0')),
            call(event=SpeechEndedEvent(audio_data='audio data 3', metadata=None)),
            call(event=PartialTranscriptionEvent(text='transcribed final text', speaker='user', speech_id='0')),
            call(event=TranscriptionEvent(text='transcribed partial text transcribed final text', speaker='user', speech_id='0')),
        ])

    @patch.object(Thread, 'start')
    @patch('voice_ui.voice_ui.logging.error')
    def test_text_to_speech(self, mock_logging_error, mock_thread_start):
        self.voice_ui._terminated = False
        self.voice_ui._config = VoiceUIConfig(voice_name='test_voice')

        def speaker_queue_get_side_effect(timeout):
            self.voice_ui._terminated = True
            return "Hello World"

        self.voice_ui._speaker_queue.get = MagicMock(side_effect=speaker_queue_get_side_effect)
        self.voice_ui._speaker_queue.task_done = MagicMock()

        self.voice_ui._text_to_speech_thread_function()

        self.voice_ui._tts_streamer.speak.assert_called_once_with(
            text='Hello World',
            voice='test_voice'
        )

        self.voice_ui._speaker_queue.get.assert_called_once()
        self.voice_ui._speaker_queue.task_done.assert_called_once()
        self.assertFalse(mock_logging_error.called)

    @patch.object(Thread, 'start')
    @patch('voice_ui.voice_ui.logging.error')
    def test_text_to_speech_queue_empty(self, mock_logging_error, mock_thread_start):
        self.voice_ui._terminated = False

        def speaker_queue_get_side_effect(timeout):
            self.voice_ui._terminated = True
            raise Empty

        self.voice_ui._speaker_queue.get = MagicMock(side_effect=speaker_queue_get_side_effect)
        self.voice_ui._text_to_speech_thread_function()
        self.assertFalse(mock_logging_error.called)

    @patch.object(Thread, 'start')
    @patch('voice_ui.voice_ui.logger.error')
    def test_text_to_speech_error_happened(self, mock_logging_error, mock_thread_start):
        self.voice_ui._terminated = False
        self.voice_ui._config = VoiceUIConfig(voice_name='test_voice')
        self.voice_ui._tts_streamer.speak = MagicMock(side_effect=Exception('Test exception'))

        inputs = ['First pass', 'Second pass']

        def speaker_queue_get_side_effect(timeout):
            if len(inputs) == 0:
                self.voice_ui._terminated = True
                raise Empty

            return inputs.pop(0)

        self.voice_ui._speaker_queue.get = MagicMock(side_effect=speaker_queue_get_side_effect)

        self.voice_ui._text_to_speech_thread_function()

        self.voice_ui._tts_streamer.speak.assert_has_calls([
            call(text='First pass', voice='test_voice'),
            call(text='Second pass', voice='test_voice'),
        ])
        self.assertTrue(mock_logging_error.called)

    def test_speak(self):
        text = "Hello world"
        self.voice_ui.speak(text)
        self.assertFalse(self.voice_ui._speaker_queue.empty())

    def test_speak_with_wait(self):
        text = "Hello world"

        # self.voice_ui._tts_streamer = MagicMock()
        self.voice_ui._tts_streamer.is_speaking = MagicMock(side_effect=[True, True, False])

        self.voice_ui.speak(text, wait=True)

        self.assertTrue(self.voice_ui._speaker_queue.empty())

        self.voice_ui._tts_streamer.speak.assert_called_once_with(
            text=text,
            voice='test_voice'
        )
        self.assertEqual(self.voice_ui._tts_streamer.is_speaking.call_count, 3)

    def test_stop_speaking(self):
        self.voice_ui._speaker_queue.put("Some text")
        self.assertFalse(self.voice_ui._speaker_queue.empty())

        self.voice_ui.stop_speaking()

        self.assertTrue(self.voice_ui._speaker_queue.empty())
        self.voice_ui._tts_streamer.stop.assert_called_once()


if __name__ == '__main__':
    unittest.main()

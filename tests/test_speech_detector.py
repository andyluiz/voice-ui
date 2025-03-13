import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

# Assuming the following imports from your module
from voice_ui.speech_detection.speech_detector import (
    AudioData,
    PartialSpeechEndedEvent,
    SpeechDetector,
    SpeechEndedEvent,
    SpeechStartedEvent,
)
from voice_ui.speech_detection.vad_microphone import MicrophoneVADStream


class TestSpeechDetector(unittest.TestCase):
    @patch('voice_ui.speech_detection.speech_detector.SpeakerProfileManager')
    def setUp(self, mock_profiler_init):
        self.callback = MagicMock()
        self.speaker_profiles_dir = Path("/path/to/speaker/profiles")

        with patch.object(MicrophoneVADStream, '__init__', return_value=None):
            self.detector = SpeechDetector(
                callback=self.callback,
                speaker_profiles_dir=self.speaker_profiles_dir,
                threshold=0.2,
                pre_speech_duration=0.1,
                post_speech_duration=1.5,
                max_speech_duration=10
            )

        self.detector._mic_stream = MagicMock(
            rate=16000,
            chunk_size=512,
            channels=1,
            sample_size=2,
        )

        mock_profiler_init.assert_called_once_with(self.speaker_profiles_dir)

    @patch('threading.Thread')
    def test_start(self, mock_thread):
        self.detector.start()

        self.assertTrue(self.detector._thread.is_alive())

        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()

    def test_stop(self):
        mock_thread = MagicMock(is_alive=MagicMock(return_value=True))
        mock_profile_manager = MagicMock()

        self.detector._profile_manager = mock_profile_manager
        self.detector._thread = mock_thread

        self.detector.stop()

        self.detector._mic_stream.pause.assert_called_once()
        mock_thread.is_alive.assert_called_once()
        mock_thread.join.assert_called_once()
        self.assertIsNone(self.detector._profile_manager)

    def test_run_with_no_callback(self):
        self.detector._callback = None
        with self.assertRaises(ValueError):
            self.detector._run()

    def test_run(self):
        self.detector._mic_stream.generator.return_value = iter([b'data'] * 2 + [b''] + [b'data'] * 3 + [b''])

        self.detector._handle_speech_start = MagicMock()
        self.detector._handle_speech_end = MagicMock()
        self.detector._handle_collected_chunks_overflow = MagicMock()

        self.detector._run()

        self.detector._mic_stream.resume.assert_called_once()
        self.detector._mic_stream.generator.assert_called_once()

        self.assertEqual(self.detector._handle_speech_start.call_count, 2)
        self.assertEqual(self.detector._handle_speech_end.call_count, 2)
        self.assertEqual(self.detector._handle_collected_chunks_overflow.call_count, 5)

        self.detector._mic_stream.pause.assert_called_once()

    def test_run_with_profile_manager(self):
        self.detector._mic_stream.generator.return_value = iter([b'data1'] * 2 + [b''] + [b'data2'] * 3 + [b''])

        self.detector._profile_manager = MagicMock()
        self.detector._profile_manager.detect_speaker.side_effect = [
            [0.9, 0.8, 0.7],
            None,
            [0.6, 0.5, 0.4],
            None,
            [0.6, 0.5, 0.4],
        ]
        self.detector._profile_manager.get_speaker_name.return_value = {'name': 'Speaker 1', 'id': 0, 'score': 1.0}

        self.detector._handle_speech_start = MagicMock()
        self.detector._handle_speech_end = MagicMock()
        self.detector._handle_collected_chunks_overflow = MagicMock()

        self.detector._run()

        self.detector._mic_stream.resume.assert_called_once()
        self.detector._mic_stream.generator.assert_called_once()

        self.detector._mic_stream.convert_data.assert_has_calls([
            call(b'data1'),
            call(b'data1'),
            call(b'data2'),
            call(b'data2'),
            call(b'data2'),
        ])
        self.assertEqual(self.detector._profile_manager.detect_speaker.call_count, 5)
        self.detector._profile_manager.get_speaker_name.assert_has_calls([
            call([0.9, 0.8, 0.7]),
            call([0.6, 0.5, 0.4]),
            call([0.6, 0.5, 0.4]),
        ])

        self.assertEqual(self.detector._handle_speech_start.call_count, 2)
        self.assertEqual(self.detector._handle_speech_end.call_count, 2)
        self.assertEqual(self.detector._handle_collected_chunks_overflow.call_count, 5)

        self.detector._mic_stream.pause.assert_called_once()

    def test_run_stream_stopped_mid_speech(self):
        self.detector._mic_stream.generator.return_value = iter([b'data'] * 5)

        self.detector._handle_speech_start = MagicMock()
        self.detector._handle_speech_end = MagicMock()
        self.detector._handle_collected_chunks_overflow = MagicMock()

        self.detector._run()

        self.detector._mic_stream.resume.assert_called_once()
        self.detector._mic_stream.generator.assert_called_once()
        self.detector._handle_speech_start.assert_called_once()
        self.detector._handle_speech_end.assert_called_once()
        self.assertEqual(self.detector._handle_collected_chunks_overflow.call_count, 5)
        self.detector._mic_stream.pause.assert_called_once()

    def test_run_stream_stopped_before_speech(self):
        self.detector._mic_stream.generator.return_value = iter([])

        self.detector._handle_speech_start = MagicMock()
        self.detector._handle_speech_end = MagicMock()
        self.detector._handle_collected_chunks_overflow = MagicMock()

        self.detector._run()

        self.detector._mic_stream.resume.assert_called_once()
        self.detector._mic_stream.generator.assert_called_once()

        self.detector._handle_speech_start.assert_not_called()
        self.detector._handle_speech_end.assert_not_called()
        self.detector._handle_collected_chunks_overflow.assert_not_called()

        self.detector._mic_stream.pause.assert_called_once()

    @patch('voice_ui.speech_detection.speech_detector.uuid4', return_value='0')
    def test_handle_speech_start(self, mock_uuid4):
        self.detector._handle_speech_start()

        mock_uuid4.assert_called_once()
        self.callback.assert_called_with(event=SpeechStartedEvent())

    @patch('voice_ui.speech_detection.speech_detector.uuid4', return_value='0')
    def test_handle_speech_end(self, mock_uuid4):
        self.detector.collected_chunks = [b'chunk1', b'chunk2']
        self.detector.speaker_scores = [[0, 1, 2, 0], [3, 0, 0, 0], [0, 4, 0, 0], [0, 0, 5, 0], [6, 7, 8, 0]]  # The expected sum is [9, 12, 15, 0]

        self.detector._profile_manager = MagicMock()
        self.detector._profile_manager.get_speaker_name.return_value = {'name': 'Speaker 1', 'id': 0, 'score': 1.0}

        self.detector._handle_speech_end()

        mock_uuid4.assert_called_once()
        self.detector._profile_manager.get_speaker_name.assert_called_once_with([9, 12, 15, 0])

        self.callback.assert_called_with(
            event=SpeechEndedEvent(
                audio_data=AudioData(
                    channels=1,
                    sample_size=2,
                    rate=16_000,
                    content=b'chunk1chunk2',
                ),
                metadata={
                    "speaker": {
                        "name": "Speaker 1",
                        "id": 0,
                        "score": 1.0,
                    }
                }
            )
        )

    def test_handle_collected_chunks_overflow(self):
        self.detector.collected_chunks = [b'\x00'] * 100
        self.detector.speaker_scores = [[0, 1, 2], [3, 4, 5], [6, 7, 8]]  # The expected average is [3, 4, 5]

        self.detector._profile_manager = MagicMock()
        self.detector._profile_manager.get_speaker_name.return_value = {'name': 'Speaker 1', 'id': 0, 'score': 1.0}

        self.detector._handle_collected_chunks_overflow(50)

        self.detector._profile_manager.get_speaker_name.assert_called_once_with([9, 12, 15])
        self.callback.assert_called_once()
        event = self.callback.call_args[1]['event']
        self.assertIsInstance(event, PartialSpeechEndedEvent)
        self.assertEqual(event.audio_data.channels, 1)
        self.assertEqual(event.audio_data.sample_size, 2)
        self.assertEqual(event.audio_data.rate, 16000)
        self.assertEqual(event.metadata['speaker']['name'], "Speaker 1")
        self.assertEqual(len(self.detector.collected_chunks), 0)

    def test_handle_collected_chunks_no_overflow(self):
        self.detector.collected_chunks = [b'\x00'] * 30
        self.detector.speaker_scores = [0.8]

        self.detector._speaker_profiles = [{"profile_data": b'data', "name": "Speaker1"}]
        self.detector._handle_collected_chunks_overflow(50)

        self.callback.assert_not_called()
        self.assertNotEqual(len(self.detector.collected_chunks), 0)


if __name__ == '__main__':
    unittest.main()

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from voice_ui.speech_detection.speaker_profile_manager import SpeakerProfileManager

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
    def setUp(self):
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

    @patch('threading.Thread')
    @patch('pveagle.create_recognizer')
    @patch.object(SpeakerProfileManager, '__init__', return_value=None)
    @patch.object(SpeakerProfileManager, 'load_profiles', return_value=[{'profile_data': b'data'}])
    def test_start(self, mock_load_profiles, mock_profiler_init, mock_create_recognizer, mock_thread):
        mock_create_recognizer.return_value = MagicMock(frame_length=512)

        with patch('os.environ', {'PORCUPINE_ACCESS_KEY': 'access_key'}):
            self.detector.start()

        self.assertTrue(self.detector._thread.is_alive())
        mock_load_profiles.assert_called_once()
        mock_create_recognizer.assert_called_once()
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()

    def test_stop(self):
        mock_thread = MagicMock(is_alive=MagicMock(return_value=True))
        mock_eagle_recognizer = MagicMock()

        self.detector._thread = mock_thread
        self.detector._eagle_recognizer = mock_eagle_recognizer

        self.detector.stop()
        self.assertIsNone(self.detector._thread)
        self.assertIsNone(self.detector._eagle_recognizer)
        mock_thread.is_alive.assert_called_once()
        mock_eagle_recognizer.delete.assert_called_once()
        self.detector._mic_stream.pause.assert_called_once()

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
        self.detector.speaker_scores = [0.9]

        self.detector._speaker_profiles = [{'name': 'Speaker 1', 'profile_data': b'data'}]
        self.detector._handle_speech_end()

        mock_uuid4.assert_called_once()

        self.callback.assert_called_with(
            event=SpeechEndedEvent(
                audio_data=AudioData(
                    channels=1,
                    sample_size=2,
                    rate=16000,
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
        self.detector.speaker_scores = [0.8]

        self.detector._speaker_profiles = [{"profile_data": b'data', "name": "Speaker1"}]
        self.detector._handle_collected_chunks_overflow(50)

        self.callback.assert_called_once()
        event = self.callback.call_args[1]['event']
        self.assertIsInstance(event, PartialSpeechEndedEvent)
        self.assertEqual(event.audio_data.channels, 1)
        self.assertEqual(event.audio_data.sample_size, 2)
        self.assertEqual(event.audio_data.rate, 16000)
        self.assertEqual(event.metadata['speaker']['name'], "Speaker1")
        self.assertEqual(len(self.detector.collected_chunks), 0)

    def test_handle_collected_chunks_no_overflow(self):
        self.detector.collected_chunks = [b'\x00'] * 30
        self.detector.speaker_scores = [0.8]

        self.detector._speaker_profiles = [{"profile_data": b'data', "name": "Speaker1"}]
        self.detector._handle_collected_chunks_overflow(50)

        self.callback.assert_not_called()
        self.assertNotEqual(len(self.detector.collected_chunks), 0)


class TestSpeechDetectorSpeakerIdentification(unittest.TestCase):
    def setUp(self):
        self.callback = MagicMock()
        with patch('voice_ui.speech_detection.speech_detector.MicrophoneVADStream') as mock_vad:
            mock_vad.return_value = None
            self.detector = SpeechDetector(
                callback=self.callback,
                speaker_profiles_dir="/test/path",
                threshold=0.2
            )

        self.detector._eagle_recognizer = MagicMock()
        self.detector._eagle_recognizer.frame_length = 512

        self.detector._speaker_profiles = [
            {"name": "Speaker1"},
            {"name": "Speaker2"},
            {"name": "Speaker3"}
        ]

    def test_detect_speaker_with_valid_frame(self):
        audio_frame = b'\x00' * 512
        expected_scores = ("Speaker1", 0, 0.95)
        self.detector._eagle_recognizer.process.return_value = expected_scores

        result = self.detector._detect_speaker(audio_frame)

        self.assertEqual(result, expected_scores)
        self.detector._eagle_recognizer.process.assert_called_once_with(audio_frame)

    def test_detect_speaker_with_no_recognizer(self):
        self.detector._eagle_recognizer = None
        audio_frame = b'\x00' * 512

        with self.assertLogs(level='ERROR') as log:
            result = self.detector._detect_speaker(audio_frame)

        self.assertIsNone(result)
        self.assertIn("Eagle recognizer is not initialized", log.output[0])

    def test_detect_speaker_with_frame_length_mismatch(self):
        audio_frame = b'\x00' * 256  # Wrong length

        with self.assertLogs(level='ERROR') as log:
            result = self.detector._detect_speaker(audio_frame)

        self.assertIsNone(result)
        self.assertIn("Frame length mismatch", log.output[0])
        self.detector._eagle_recognizer.process.assert_not_called()

    def test_detect_speaker_with_no_detection(self):
        audio_frame = b'\x00' * 512
        self.detector._eagle_recognizer.process.return_value = None

        with self.assertLogs(level='DEBUG') as log:
            result = self.detector._detect_speaker(audio_frame)

        self.assertIsNone(result)
        self.assertIn("No speaker detected", log.output[0])
        self.detector._eagle_recognizer.process.assert_called_once_with(audio_frame)

    def test_get_speaker_name_empty_scores(self):
        result = self.detector._get_speaker_name([])
        self.assertIsNone(result)

    def test_get_speaker_name_below_threshold(self):
        scores = [0.1, 0.15, 0.19]
        result = self.detector._get_speaker_name(scores)
        self.assertIsNone(result)

    def test_get_speaker_name_valid_score(self):
        scores = [0.3, 0.8, 0.5]
        result = self.detector._get_speaker_name(scores)
        expected = {
            "name": "Speaker2",
            "id": 1,
            "score": 0.8
        }
        self.assertEqual(result, expected)

    def test_get_speaker_name_multiple_speakers_same_score(self):
        scores = [0.9, 0.9, 0.5]
        result = self.detector._get_speaker_name(scores)
        expected = {
            "name": "Speaker1",
            "id": 0,
            "score": 0.9
        }
        self.assertEqual(result, expected)

    def test_get_speaker_name_threshold_exact(self):
        scores = [0.2, 0.1, 0.15]
        result = self.detector._get_speaker_name(scores)
        expected = {
            "name": "Speaker1",
            "id": 0,
            "score": 0.2
        }
        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()

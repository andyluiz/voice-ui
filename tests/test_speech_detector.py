import unittest
from collections import deque
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from voice_ui.speech_detection.speaker_profile_manager import SpeakerProfileManager

# Assuming the following imports from your module
from voice_ui.speech_detection.speech_detector import (
    AudioData,
    MetaDataEvent,
    PartialSpeechEndedEvent,
    SpeechDetector,
    SpeechEndedEvent,
    SpeechStartedEvent,
)
from voice_ui.speech_detection.vad_microphone import MicrophoneVADStream


def mock_mic_stream_init(self, *args, **kwargs):
    self._pv_access_key = None
    self._cobra = MagicMock(frame_length=512)
    self._rate = 16000
    self._chunk = 512
    self._channels = 1
    self._sample_size = 2
    self._sampleformat = "int16"
    # self._buff = MagicMock(get=MagicMock(return_value=None))

    # self._pre_speech_queue = MagicMock(get=MagicMock(return_value=None))
    self._audio_interface = MagicMock(get_sample_size=MagicMock(return_value=self._sample_size))
    # self._audio_stream = MagicMock()


class TestSpeechDetector(unittest.TestCase):
    def setUp(self):
        self.callback = MagicMock()
        self.speaker_profiles_dir = Path("/path/to/speaker/profiles")

        with patch.object(MicrophoneVADStream, '__init__', mock_mic_stream_init):
            self.detector = SpeechDetector(
                callback=self.callback,
                speaker_profiles_dir=self.speaker_profiles_dir,
                threshold=0.2,
                pre_speech_duration=0.1,
                post_speech_duration=1.5,
                max_speech_duration=10
            )

    @patch('threading.Thread')
    @patch('pveagle.create_recognizer')
    @patch.object(SpeakerProfileManager, '__init__', return_value=None)
    @patch.object(SpeakerProfileManager, 'load_profiles', return_value=[{'profile_data': b'data'}])
    def test_start(self, mock_load_profiles, mock_profiler_init, mock_create_recognizer, mock_thread):
        mock_create_recognizer.return_value = MagicMock(frame_length=512)

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
        self.detector.pause = MagicMock()

        self.detector.stop()
        self.assertIsNone(self.detector._thread)
        self.assertIsNone(self.detector._eagle_recognizer)
        mock_thread.is_alive.assert_called_once()
        mock_eagle_recognizer.delete.assert_called_once()
        self.detector.pause.assert_called_once()

    def test_run_with_no_callback(self):
        with self.assertRaises(ValueError):
            self.detector._run(callback=None)

    def test_run(self):
        def process_chunk_side_effect(*args, **kwargs):
            if self.detector._process_next_chunk.call_count > 5:
                self.detector._closed = True

        self.detector._process_next_chunk = MagicMock(side_effect=process_chunk_side_effect)
        self.detector._speaker_profiles = [{'name': 'Speaker 1', 'profile_data': b'data'}]
        self.detector.resume = MagicMock()
        self.detector.pause = MagicMock()
        self.detector._closed = False

        self.detector._run(**self.detector._thread_args)

        self.detector.resume.assert_called_once()
        self.assertEqual(self.detector._process_next_chunk.call_count, 6)
        self.detector._process_next_chunk.assert_has_calls([
            call(
                self.callback,
                0.2,
                4,
                47,
                313
            )
        ] * 6)
        self.detector.pause.assert_called_once()

    def test_process_next_chunk_no_event(self):
        # Setup mock methods and attributes
        self.detector._get_chunk_from_buffer = MagicMock(return_value=b'chunk')
        self.detector._convert_data = MagicMock(return_value=b'audio_frame')
        self.detector._cobra = MagicMock()
        self.detector._cobra.process = MagicMock(return_value=0.3)
        self.detector._speaker_profiles = [{'name': 'Speaker 1', 'profile_data': b'data'}]

        self.detector.threshold_counter = deque(maxlen=10)
        self.detector.speech_detected = False
        self.detector.above_threshold_counter = 0
        self.detector.below_threshold_counter = 0
        self.detector.collected_chunks = []
        self.detector.speaker_scores = [0]

        self.detector._handle_speech_start = MagicMock()
        self.detector._handle_speech_end = MagicMock()
        self.detector._handle_metadata_report = MagicMock()
        self.detector._handle_collected_chunks_overflow = MagicMock()

        self.detector._process_next_chunk(
            callback=self.callback,
            threshold=0.2,
            start_chunks=5,
            end_chunks=5,
            max_chunks=50
        )

        self.detector._get_chunk_from_buffer.assert_called_once()
        self.detector._convert_data.assert_called_once()
        self.detector._cobra.process.assert_called_once()

        self.assertEqual(self.detector.above_threshold_counter, 1)
        self.assertEqual(len(self.detector.threshold_counter), 1)
        # self.callback.assert_called()

        self.detector._handle_speech_start.assert_not_called()
        self.detector._handle_speech_end.assert_not_called()
        self.detector._handle_metadata_report.assert_called_once()
        self.detector._handle_collected_chunks_overflow.assert_not_called()

    def test_process_next_chunk_speech_start(self):
        # Setup mock methods and attributes
        self.detector._get_chunk_from_buffer = MagicMock(return_value=b'chunk')
        self.detector._convert_data = MagicMock(return_value=b'audio_frame')
        self.detector._cobra = MagicMock()
        self.detector._cobra.process = MagicMock(return_value=0.5)
        self.detector._speaker_profiles = [{'name': 'Speaker 1', 'profile_data': b'data'}]

        self.detector.threshold_counter = deque(maxlen=10)
        self.detector.speech_detected = False
        self.detector.above_threshold_counter = 5
        self.detector.below_threshold_counter = 0
        self.detector.collected_chunks = []
        self.detector.speaker_scores = [0]
        self.detector._detect_speaker = MagicMock(return_value=[0.5])

        self.detector._handle_speech_start = MagicMock()
        self.detector._handle_speech_end = MagicMock()
        self.detector._handle_metadata_report = MagicMock()
        self.detector._handle_collected_chunks_overflow = MagicMock()

        self.detector._process_next_chunk(
            callback=self.callback,
            threshold=0.2,
            start_chunks=5,
            end_chunks=5,
            max_chunks=50
        )

        self.detector._get_chunk_from_buffer.assert_called_once()
        self.detector._convert_data.assert_called_once()
        self.detector._cobra.process.assert_called_once()

        self.assertEqual(self.detector.above_threshold_counter, 6)
        self.assertEqual(len(self.detector.threshold_counter), 1)

        self.detector._handle_speech_start.assert_called_once_with(self.callback)
        self.detector._handle_speech_end.assert_not_called()
        self.detector._handle_metadata_report.assert_called_once_with(self.callback, 0.5)
        self.detector._handle_collected_chunks_overflow.assert_called_once_with(self.callback, 50)

    def test_process_next_chunk_speech_end(self):
        # Setup mock methods and attributes
        self.detector._get_chunk_from_buffer = MagicMock(return_value=b'chunk')
        self.detector._convert_data = MagicMock(return_value=b'audio_frame')
        self.detector._cobra = MagicMock()
        self.detector._cobra.process = MagicMock(return_value=0.1)
        self.detector._speaker_profiles = [{'name': 'Speaker 1', 'profile_data': b'data'}]

        self.detector.threshold_counter = deque(maxlen=10)
        self.detector.speech_detected = True
        self.detector.above_threshold_counter = 0
        self.detector.below_threshold_counter = 5
        self.detector.collected_chunks = []
        self.detector.speaker_scores = [0]
        self.detector._detect_speaker = MagicMock(return_value=[0.0])

        self.detector._handle_speech_start = MagicMock()
        self.detector._handle_speech_end = MagicMock()
        self.detector._handle_metadata_report = MagicMock()
        self.detector._handle_collected_chunks_overflow = MagicMock()

        self.detector._process_next_chunk(
            callback=self.callback,
            threshold=0.2,
            start_chunks=5,
            end_chunks=5,
            max_chunks=50
        )

        self.detector._get_chunk_from_buffer.assert_called_once()
        self.detector._convert_data.assert_called_once()
        self.detector._cobra.process.assert_called_once()

        self.assertEqual(self.detector.below_threshold_counter, 6)
        self.assertEqual(len(self.detector.threshold_counter), 1)

        self.detector._handle_speech_start.assert_not_called()
        self.detector._handle_speech_end.assert_called_once_with(self.callback)
        self.detector._handle_metadata_report.assert_called_once_with(self.callback, 0.1)
        self.detector._handle_collected_chunks_overflow.assert_not_called()

    @patch('voice_ui.speech_detection.speech_detector.uuid4', return_value='0')
    def test_handle_speech_start(self, mock_uuid4):
        self.detector.speech_detected = False
        self.detector._pre_speech_queue = [b'chunk1', b'chunk2']
        self.detector.collected_chunks = []

        self.detector._handle_speech_start(self.callback)
        self.assertIn(b'chunk1', self.detector.collected_chunks)
        self.assertIn(b'chunk2', self.detector.collected_chunks)

        mock_uuid4.assert_called_once()

        self.callback.assert_called_with(event=SpeechStartedEvent())

    @patch('voice_ui.speech_detection.speech_detector.uuid4', return_value='0')
    def test_handle_speech_end(self, mock_uuid4):
        self.detector.collected_chunks = [b'chunk1', b'chunk2']
        self.detector.speaker_scores = [0.9]

        self.detector._speaker_profiles = [{'name': 'Speaker 1', 'profile_data': b'data'}]
        self.detector._handle_speech_end(self.callback)

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

    @patch('voice_ui.speech_detection.speech_detector.uuid4', return_value='0')
    def test_handle_metadata_report(self, mock_uuid4):
        self.detector.above_threshold_counter = 0
        self.detector.below_threshold_counter = 0

        self.detector._handle_metadata_report(self.callback, 0.5)

        mock_uuid4.assert_called_once()

        self.callback.assert_called_once_with(
            event=MetaDataEvent(
                metadata={
                    "voice_probability": 0.5,
                    "above_threshold_counter": 0,
                    "below_threshold_counter": 0,
                },
            )
        )

    def test_handle_collected_chunks_overflow(self):
        self.detector.collected_chunks = [b'\x00'] * 100
        self.detector.speaker_scores = [0.8]
        self.detector.below_threshold_counter = 6

        self.detector._speaker_profiles = [{"profile_data": b'data', "name": "Speaker1"}]
        self.detector._handle_collected_chunks_overflow(self.callback, 50)

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
        self.detector.below_threshold_counter = 4

        self.detector._speaker_profiles = [{"profile_data": b'data', "name": "Speaker1"}]
        self.detector._handle_collected_chunks_overflow(self.callback, 50)

        self.callback.assert_not_called()
        self.assertNotEqual(len(self.detector.collected_chunks), 0)


if __name__ == '__main__':
    unittest.main()

import os
import queue
import unittest
from datetime import datetime, timedelta
from typing import KeysView
from unittest.mock import MagicMock, call, patch

from voice_ui.speech_detection.vad_microphone import (
    HotwordDetector,
    MicrophoneStream,
    MicrophoneVADStream,
)


class TestHotwordDetector(unittest.TestCase):

    @patch('pvporcupine.create', return_value=MagicMock())
    def setUp(self, mock_create):
        os.environ['PORCUPINE_ACCESS_KEY'] = '1234'
        self.detector = HotwordDetector()
        self.mock_create = mock_create

    def test_init_with_default_keywords(self):
        self.assertEqual(self.detector._handle, self.mock_create.return_value)
        self.mock_create.assert_called_once()

    @patch('os.path.exists')
    @patch('os.path.abspath', return_value='mock_path')
    def test_available_keyword_paths(self, mock_abspath, mock_path_exists):
        mock_path_exists.return_value = True

        self.detector._additional_keyword_paths = {
            'selena': '/some/resources/dir/Selena_en_raspberry-pi_v3_0_0.ppn',
            'artemis': '/some/resources/dir/Artemis_en_raspberry-pi_v3_0_0.ppn'
        }

        keyword_paths = self.detector.available_keyword_paths()

        self.assertEqual(mock_path_exists.call_count, 2)
        mock_path_exists.assert_has_calls([
            call('/some/resources/dir/Selena_en_raspberry-pi_v3_0_0.ppn'),
            call('/some/resources/dir/Artemis_en_raspberry-pi_v3_0_0.ppn'),
        ])
        self.assertIn('selena', keyword_paths)
        self.assertEqual(keyword_paths['selena'], 'mock_path')

    def test_available_keywords(self):
        keywords = self.detector.available_keywords()
        self.assertIsInstance(keywords, KeysView)

    def test_process_with_incorrect_audio_frame_length(self):
        incorrect_audio_frame = [0] * (self.detector._handle.frame_length + 1)
        with self.assertRaises(ValueError):
            self.detector.process(incorrect_audio_frame)

    def test_process_with_correct_audio_frame_length(self):
        self.detector._handle.frame_length = 512
        correct_audio_frame = [0] * self.detector._handle.frame_length

        self.detector._handle.process.return_value = True

        result = self.detector.process(correct_audio_frame)

        self.detector._handle.process.assert_called_once()
        self.assertTrue(result)


def mock_mic_stream_init(self, chunk):
    self._rate = 16000
    self._chunk = chunk
    self._buff = MagicMock()
    self._audio_interface = MagicMock()
    self._audio_stream = MagicMock()


class TestMicrophoneVADStream(unittest.TestCase):

    @patch('pvcobra.create')
    def setUp(self, mock_cobra_create):
        self.mock_cobra = MagicMock(frame_length=512)
        mock_cobra_create.return_value = self.mock_cobra

        with patch.object(MicrophoneStream, '__init__', mock_mic_stream_init):
            self.stream = MicrophoneVADStream()

        self.assertEqual(self.stream._cobra, self.mock_cobra)

    @patch('pvcobra.create', return_value=MagicMock())
    def test_init_with_audio_length_out_of_limits_negative(self, mock_create):
        self.mock_cobra = mock_create
        self.mock_cobra.return_value = MagicMock(frame_length=512)

        with patch.object(MicrophoneStream, '__init__', mock_mic_stream_init):
            self.stream = MicrophoneVADStream(pre_speech_audio_length=-1)

        self.assertEqual(self.stream._cobra, self.mock_cobra.return_value)
        self.assertEqual(self.stream._pre_speech_queue.maxlen, 1)
        self.mock_cobra.assert_called_once()

    @patch('pvcobra.create', return_value=MagicMock())
    def test_init_with_audio_length_out_of_limits_high(self, mock_create):
        self.mock_cobra = mock_create
        self.mock_cobra.return_value = MagicMock(frame_length=512)

        with patch.object(MicrophoneStream, '__init__', mock_mic_stream_init):
            self.stream = MicrophoneVADStream(pre_speech_audio_length=10)

        self.assertEqual(self.stream._cobra, self.mock_cobra.return_value)
        self.assertEqual(self.stream._pre_speech_queue.maxlen, 150)
        self.mock_cobra.assert_called_once()

    def test_delete(self):
        self.stream._cobra.delete = MagicMock()
        self.stream.__del__()
        self.stream._cobra.delete.assert_called_once()

    def test_exit(self):
        self.stream._cobra.delete = MagicMock()
        self.stream.__exit__(None, None, None)
        self.stream._cobra.delete.assert_called_once()

    def test_convert_data(self):
        byte_data = b'\x01\x02\x03\x04'
        result = MicrophoneVADStream._convert_data(byte_data)
        self.assertEqual(result, [513, 1027])

    def test_timer_expired_with_no_timeout(self):
        start_time = datetime.now()
        result = MicrophoneVADStream._timer_expired(start_time)
        self.assertEqual(result, False)

    def test_timer_expired_with_timeout_expired(self):
        start_time = datetime.now() - timedelta(seconds=1)
        result = MicrophoneVADStream._timer_expired(start_time, timeout=1)
        self.assertEqual(result, True)

    def test_timer_expired_with_timeout_not_expired(self):
        start_time = datetime.now() - timedelta(seconds=1)
        result = MicrophoneVADStream._timer_expired(start_time, timeout=10)
        self.assertEqual(result, False)

    def test_pause(self):
        with patch('voice_ui.audio_io.microphone.MicrophoneStream.pause', return_value=None) as mock_super_pause:
            self.stream.pause()

        mock_super_pause.assert_called_once()
        self.assertEqual(len(self.stream._pre_speech_queue), 0)

    def test_get_chunk_from_buffer_with_empty_queue(self):
        self.stream._buff.get.return_value = None
        chunk = self.stream._get_chunk_from_buffer()
        self.assertIsNone(chunk)
        self.stream._buff.get.assert_called_once_with(timeout=0.05)

    def test_get_chunk_from_buffer_with_non_empty_queue(self):
        self.stream._buff.get.return_value = b'\x01\x02\x03\x04'

        chunk = self.stream._get_chunk_from_buffer()

        self.assertIsNotNone(chunk)
        self.assertEqual(chunk, b'\x01\x02\x03\x04')
        self.assertEqual(len(self.stream._pre_speech_queue), 1)
        self.stream._buff.get.assert_called_once_with(timeout=0.05)

    def test_detect_speech_no_voice(self):
        def stream_side_effect(timeout=None):
            if self.stream._buff.get.call_count >= 2 * 4:  # 4 is above_threshold
                self.stream._closed = True

            if self.stream._buff.get.call_count % 2 == 0:
                raise queue.Empty
            else:
                return b'\x01\x01' * self.mock_cobra.frame_length

        self.stream._buff.get.side_effect = stream_side_effect
        self.stream._threshold = 0.7

        self.mock_cobra.process.return_value = 0.5  # Below threshold

        result, speaker_scores = self.stream.detect_speech(timeout=0.1)

        self.assertFalse(result)
        self.assertEqual(speaker_scores, -1)
        self.assertEqual(self.mock_cobra.process.call_count, 4)

    def test_detect_speech_runtime_error(self):
        self.stream._buff.get.return_value = None

        with self.assertRaises(RuntimeError):
            self.stream.detect_speech()

        self.mock_cobra.process.assert_not_called()

    def test_detect_speech_timeout(self):
        def stream_side_effect(timeout=None):
            raise queue.Empty

        self.stream._buff.get.side_effect = stream_side_effect

        with self.assertRaises(TimeoutError):
            self.stream.detect_speech(timeout=0.01)

        self.mock_cobra.process.assert_not_called()

    def test_detect_speech_with_voice_no_profiles(self):
        self.stream._buff.get.return_value = b'\x01\x01' * self.mock_cobra.frame_length

        self.mock_cobra.process.return_value = 0.8  # Above threshold

        result, speaker_scores = self.stream.detect_speech(threshold=0.7)

        self.assertTrue(result)
        self.assertIsInstance(speaker_scores, list)
        self.assertEqual(self.mock_cobra.process.call_count, 5)

    @patch('pveagle.create_recognizer')
    def test_detect_speech_with_voice_with_profiles(self, mock_create_recognizer):
        self.stream._buff.get.return_value = b'\x01\x01' * self.mock_cobra.frame_length

        mock_create_recognizer.return_value = MagicMock(frame_length=512)
        mock_create_recognizer.return_value.process.return_value = [0.1, 0.3]

        self.mock_cobra.process.return_value = 0.8  # Above threshold

        result, speaker_scores = self.stream.detect_speech(timeout=0.1, speaker_profiles=['Speaker 1', 'Speaker 2'])

        self.assertTrue(result)
        self.assertIsInstance(speaker_scores, list)
        self.assertEqual(speaker_scores, [0.1, 0.3])

        self.assertEqual(self.mock_cobra.process.call_count, 5)
        self.assertEqual(mock_create_recognizer.return_value.process.call_count, self.mock_cobra.process.call_count)
        mock_create_recognizer.return_value.delete.assert_called_once()

    @patch('pvporcupine.create')
    @patch.object(HotwordDetector, 'process', return_value=-1)
    def test_detect_hot_keyword_no_keyword(self, mock_process, mock_porcupine_create):
        self.stream._buff.get.side_effect = [
            b'\x00\x00' * self.mock_cobra.frame_length,
            b'\x00\x00' * self.mock_cobra.frame_length,
            b'\x00\x00' * self.mock_cobra.frame_length,
            None
        ]

        with self.assertRaises(RuntimeError):
            self.stream.detect_hot_keyword()

        self.assertEqual(mock_process.call_count, 3)

    @patch('pvporcupine.create')
    @patch.object(HotwordDetector, 'process', return_value=1)
    def test_detect_hot_keyword_with_keyword(self, mock_process, mock_porcupine_create):
        self.stream._buff.get.side_effect = [
            queue.Empty,
            b'\x00\x00' * self.mock_cobra.frame_length,
            None
        ]

        result = self.stream.detect_hot_keyword()
        self.assertTrue(result)
        self.assertEqual(mock_process.call_count, 1)

    @patch('pvporcupine.create')
    def test_detect_hot_keyword_shutdown(self, mock_porcupine_create):
        def stream_side_effect(timeout=None):
            if self.stream._buff.get.call_count >= 2:
                self.stream._closed = True
            raise queue.Empty

        self.stream._buff.get.side_effect = stream_side_effect

        result = self.stream.detect_hot_keyword()
        self.assertFalse(result)

        self.assertEqual(self.stream._buff.get.call_count, 2)


if __name__ == '__main__':
    unittest.main()

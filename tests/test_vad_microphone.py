import os
import queue
import time
import unittest
from collections import deque
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


def mock_mic_stream_init(self, rate, chunk):
    self._rate = rate
    self._chunk = chunk
    self._buff = MagicMock()
    self._audio_interface = MagicMock()
    self._audio_stream = MagicMock()


class TestMicrophoneVADStream(unittest.TestCase):

    @patch('voice_ui.voice_activity_detection.vad_factory.VADFactory.create')
    def setUp(self, mock_vad_factory_create):
        self.mock_vad = MagicMock(frame_length=512)
        mock_vad_factory_create.return_value = self.mock_vad

        with patch.object(MicrophoneStream, '__init__', mock_mic_stream_init):
            self.stream = MicrophoneVADStream()

        self.assertEqual(self.stream._vad, self.mock_vad)

    @patch('voice_ui.voice_activity_detection.vad_factory.VADFactory.create')
    def test_init_with_audio_length_out_of_limits_negative(self, mock_vad_factory_create):
        self.mock_vad = MagicMock(frame_length=512)
        mock_vad_factory_create.return_value = self.mock_vad

        with patch.object(MicrophoneStream, '__init__', mock_mic_stream_init):
            self.stream = MicrophoneVADStream(pre_speech_duration=-1)

        self.assertEqual(self.stream._vad, self.mock_vad)
        self.assertEqual(self.stream._pre_speech_queue.maxlen, 1)
        mock_vad_factory_create.assert_called_once()

    @patch('voice_ui.voice_activity_detection.vad_factory.VADFactory.create')
    def test_init_with_audio_length_out_of_limits_high(self, mock_vad_factory_create):
        self.mock_vad = MagicMock(frame_length=512)
        mock_vad_factory_create.return_value = self.mock_vad

        with patch.object(MicrophoneStream, '__init__', mock_mic_stream_init):
            self.stream = MicrophoneVADStream(pre_speech_duration=10)

        self.assertEqual(self.stream._vad, self.mock_vad)
        self.assertEqual(self.stream._pre_speech_queue.maxlen, 150)
        mock_vad_factory_create.assert_called_once()

    def test_convert_data(self):
        byte_data = b'\x01\x02\x03\x04'
        result = MicrophoneVADStream.convert_data(byte_data)
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
                return b'\x01\x01' * self.mock_vad.frame_length

        self.stream._buff.get.side_effect = stream_side_effect

        self.mock_vad.process.return_value = False  # Below threshold

        result = list(self.stream.generator())

        self.assertListEqual(result, [])
        self.assertEqual(self.mock_vad.process.call_count, 4)

    def test_detect_speech(self):
        def stream_side_effect(timeout=None):
            if self.stream._buff.get.call_count >= 20:  # 4 is above_threshold
                self.stream._closed = True

            return bytes([self.stream._buff.get.call_count])

        self.stream._pre_speech_queue = deque(maxlen=2)  # Limit pre_speech_queue to 2
        self.stream._buff.get.side_effect = stream_side_effect
        self.mock_vad.process.side_effect = [
            False,  # 1
            False,
            False,
            True,   # Speech started here. This plus two previous frames should be returned.
            True,   # Speech in progress. This frame should be returned.
            True,   # Speech in progress. This frame should be returned.
            False,  # Speech stopped here.
            False,
            False,
            False,  # 10 (\x0a)
            True,   # Speech started here again. This plus two previous frames should be returned.
            True,   # Speech in progress. This frame should be returned.
            True,   # Speech in progress. This frame should be returned.
            True,   # Speech in progress. This frame should be returned.
            True,   # Speech in progress. This frame should be returned.
            False,  # Speech stopped here.
            False,
            False,
            False,
            False,  # 20 (\x14)
        ]

        result = list(self.stream.generator())

        self.assertListEqual(result, [b"\x02\x03\x04", b"\x05", b"\x06", b"", b"\x09\x0a\x0b", b"\x0c", b"\x0d", b"\x0e", b"\x0f", b""])
        self.assertEqual(self.mock_vad.process.call_count, 20)

    def test_detect_speech_runtime_error(self):
        self.stream._buff.get.return_value = None

        with self.assertRaises(RuntimeError):
            list(self.stream.generator())

        self.mock_vad.process.assert_not_called()

    def test_detect_speech_timeout(self):
        def stream_side_effect(timeout=None):
            time.sleep(0.002)

            if self.stream._buff.get.call_count >= 2 * 4:  # 4 is above_threshold
                self.stream._closed = True

            if self.stream._buff.get.call_count % 2 == 0:
                raise queue.Empty
            else:
                return b'\x01\x01' * self.mock_vad.frame_length

        self.stream._buff.get.side_effect = stream_side_effect
        self.stream._detection_timeout = 0.001

        self.mock_vad.process.return_value = False  # Below threshold

        with self.assertRaises(TimeoutError):
            list(self.stream.generator())

        self.assertEqual(self.mock_vad.process.call_count, 1)

    @patch('pvporcupine.create')
    @patch.object(HotwordDetector, 'process', return_value=-1)
    def test_detect_hot_keyword_no_keyword(self, mock_process, mock_porcupine_create):
        self.stream._buff.get.side_effect = [
            b'\x00\x00' * self.mock_vad.frame_length,
            b'\x00\x00' * self.mock_vad.frame_length,
            b'\x00\x00' * self.mock_vad.frame_length,
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
            b'\x00\x00' * self.mock_vad.frame_length,
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

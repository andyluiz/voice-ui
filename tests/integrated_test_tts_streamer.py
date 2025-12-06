import logging
import threading
import time
import unittest

import dotenv

from voice_ui.speech_synthesis import TTSFactory


class TestTextToSpeechAudioStreamer(unittest.TestCase):
    def setUp(self):
        dotenv.load_dotenv()

        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(levelname)s %(message)s',
            handlers=[
                logging.StreamHandler(),
            ],
        )

    def test_speak(self):
        streamer = TTSFactory.create("openai-tts")

        # Capture audio data using a thread-safe mechanism
        captured_audio = []
        audio_lock = threading.Lock()
        original_put = streamer._data_queue.put

        def capture_and_queue(item, *args, **kwargs):
            """Intercept queue.put to capture audio data"""
            with audio_lock:
                if item:
                    captured_audio.append(item)
            return original_put(item, *args, **kwargs)

        # Replace the queue.put method to capture audio
        streamer._data_queue.put = capture_and_queue

        test_text = " ".join([
            "Even broken in spirit as he is, no one can feel more deeply than he does the beauties of nature.",
            "The starry sky, the sea, and every sight afforded by these wonderful regions, seems still to have the power of elevating his soul from earth.",
            "Such a man has a double existence: he may suffer misery, and be overwhelmed by disappointments; yet, when he has retired into himself, he will be like a celestial spirit that has a halo around him, within whose circle no grief or folly ventures."
        ])

        def speaker():
            print('Speaking')
            streamer.speak(test_text)

        speaker_thread = threading.Thread(target=speaker, daemon=True)
        speaker_thread.start()

        print('Waiting for speaker thread to start...')
        time.sleep(10)

        # Wait for audio data to be captured
        time.sleep(2)

        with audio_lock:
            audio_bytes = b"".join(captured_audio)

        self.assertGreater(len(captured_audio), 0, "Audio data should have been generated")

        # Verify audio data is substantial
        self.assertGreater(len(audio_bytes), 100, "Audio data should be substantial")

        # Verify audio duration is reasonable (text is ~150 words, should be ~30-50 seconds of audio)
        # Audio is at 24000 Hz, so roughly 720000-1200000 bytes for 30-50 seconds
        expected_min_bytes = 300000  # ~12.5 seconds at 24kHz
        self.assertGreater(
            len(audio_bytes),
            expected_min_bytes,
            f"Audio should be at least {expected_min_bytes} bytes, got {len(audio_bytes)}"
        )

        print(f"Queue size: {streamer.speech_queue_size()}")
        print(f"Total audio data: {len(audio_bytes)} bytes ({len(captured_audio)} chunks)")

        print('Stopping streamer...')
        self.assertFalse(streamer.is_stopped())
        streamer.stop()
        self.assertTrue(streamer.is_stopped())

        time.sleep(1)

        self.assertTrue(streamer._speaker_thread.is_alive())
        self.assertEqual(streamer.speech_queue_size(), 0)

        print('Waiting to check whether the audio stopped...')
        time.sleep(2)

        self.assertTrue(streamer._speaker_thread.is_alive())
        streamer.__del__()
        self.assertFalse(streamer._speaker_thread.is_alive())


if __name__ == '__main__':
    unittest.main()

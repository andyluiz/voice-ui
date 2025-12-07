import logging
import threading
import time
import unittest

import dotenv

from voice_ui.audio_io.player import Player
from voice_ui.speech_synthesis import TTSFactory


class CapturingPlayer(Player):
    """Mock player that captures audio data for testing."""

    def __init__(self):
        """Initialize the capturing player without parent init (to avoid PyAudio)."""
        self.captured_audio = []
        self.audio_lock = threading.Lock()

        # Set up minimal attributes to satisfy Player.__del__
        self._stream = None
        self._audio_interface = None
        # super().__init__()

    def play_data(self, audio_data):
        """Capture audio data instead of playing it."""
        with self.audio_lock:
            if audio_data:
                self.captured_audio.append(audio_data)
                # super().play_data(audio_data)

    def terminate(self):
        """No-op for mock player."""
        pass

    def __del__(self):
        """Override to avoid calling stop_stream on None."""
        # No cleanup needed for mock player
        pass


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
        # Create a capturing player to inject as dependency
        player = CapturingPlayer()

        # Create streamer with dependency injection
        streamer = TTSFactory.create("openai-tts", player=player)

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

        with player.audio_lock:
            audio_bytes = b"".join(player.captured_audio)

        self.assertGreater(len(player.captured_audio), 0, "Audio data should have been generated")

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
        print(f"Total audio data: {len(audio_bytes)} bytes ({len(player.captured_audio)} chunks)")

        print('Stopping streamer...')
        self.assertFalse(streamer.is_stopped())
        streamer.stop()
        self.assertTrue(streamer.is_stopped())

        time.sleep(1)

        self.assertTrue(streamer._queued_player._speaker_thread.is_alive())
        self.assertEqual(streamer.speech_queue_size(), 0)

        print('Waiting to check whether the audio stopped...')
        time.sleep(2)

        self.assertTrue(streamer._queued_player._speaker_thread.is_alive())
        streamer.__del__()
        self.assertFalse(streamer._queued_player._speaker_thread.is_alive())

    def test_google_speak(self):
        # Create a capturing player to inject as dependency
        player = CapturingPlayer()

        # Create streamer with dependency injection
        streamer = TTSFactory.create("google", player=player)

        test_text = " ".join([
            "Even broken in spirit as he is, no one can feel more deeply than he does the beauties of nature.",
            "The starry sky, the sea, and every sight afforded by these wonderful regions, seems still to have the power of elevating his soul from earth.",
        ])

        def speaker():
            print('Speaking with Google TTS')
            streamer.speak(test_text)

        speaker_thread = threading.Thread(target=speaker, daemon=True)
        speaker_thread.start()

        print('Waiting for Google speaker thread to start...')
        time.sleep(10)

        # Wait for audio data to be captured
        time.sleep(2)

        with player.audio_lock:
            audio_bytes = b"".join(player.captured_audio)

        self.assertGreater(len(player.captured_audio), 0, "Audio data should have been generated from Google TTS")

        # Verify audio data is substantial
        self.assertGreater(len(audio_bytes), 100, "Audio data should be substantial")

        print(f"Queue size: {streamer.speech_queue_size()}")
        print(f"Total audio data: {len(audio_bytes)} bytes ({len(player.captured_audio)} chunks)")

        print('Stopping Google streamer...')
        self.assertFalse(streamer.is_stopped())
        streamer.stop()
        self.assertTrue(streamer.is_stopped())

        time.sleep(1)

        self.assertTrue(streamer._queued_player._speaker_thread.is_alive())
        self.assertEqual(streamer.speech_queue_size(), 0)

        print('Waiting to check whether the audio stopped...')
        time.sleep(2)

        self.assertTrue(streamer._queued_player._speaker_thread.is_alive())
        streamer.__del__()
        self.assertFalse(streamer._queued_player._speaker_thread.is_alive())


if __name__ == '__main__':
    unittest.main()

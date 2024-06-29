import logging
import threading
import time
import unittest

import dotenv
from voice_ui.speech_synthesis.text_to_speech_streamer import TextToSpeechAudioStreamer


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
        streamer = TextToSpeechAudioStreamer()

        def speaker():
            print('Speaking')
            streamer.speak(
                " ".join([
                    "Even broken in spirit as he is, no one can feel more deeply than he does the beauties of nature.",
                    "The starry sky, the sea, and every sight afforded by these wonderful regions, seems still to have the power of elevating his soul from earth.",
                    "Such a man has a double existence: he may suffer misery, and be overwhelmed by disappointments; yet, when he has retired into himself, he will be like a celestial spirit that has a halo around him, within whose circle no grief or folly ventures."
                ])
            )

        speaker_thread = threading.Thread(target=speaker, daemon=True)
        speaker_thread.start()

        print('Waiting for speaker thread to start...')
        time.sleep(10)

        self.assertGreater(streamer._audio_bytes_queue.qsize(), 0)
        print(f"Queue size: {streamer._audio_bytes_queue.qsize()}")

        print('Stopping streamer...')
        self.assertFalse(streamer.is_stopped())
        streamer.stop()
        self.assertTrue(streamer.is_stopped())

        time.sleep(1)

        self.assertTrue(streamer._speaker_thread.is_alive())
        self.assertEqual(streamer._audio_bytes_queue.qsize(), 0)

        print('Waiting to check whether the audio stopped...')
        time.sleep(2)

        self.assertTrue(streamer._speaker_thread.is_alive())
        streamer.__del__()
        self.assertFalse(streamer._speaker_thread.is_alive())


if __name__ == '__main__':
    unittest.main()

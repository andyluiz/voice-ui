import time
import unittest

from voice_ui.audio_io.audio_data import AudioData
from voice_ui.speech_synthesis import pass_through_text_to_speech_streamer as pts_mod


class FakePlayer:
    def __init__(self):
        self.played = []

    def play_data(self, data):
        # simulate a small delay
        self.played.append(data)


class TestPassThroughStreamer(unittest.TestCase):
    def test_bytequeue_put_get_and_timeout(self):
        bq = pts_mod.ByteQueue()

        # without any put, the internal semaphore initially allows a get
        # but no data has been added, so get should return empty bytes
        got_empty = bq.get(timeout=0.1)
        self.assertEqual(got_empty, b'')

        # after put, get should return the data
        bq.put(b'hello')
        got = bq.get(timeout=0.5)
        self.assertEqual(got, b'hello')

    def test_speak_and_terminate_uses_player(self):
        # Patch Player to avoid pyaudio
        orig_player = pts_mod.Player
        pts_mod.Player = FakePlayer

        try:
            streamer = pts_mod.PassThroughTextToSpeechAudioStreamer()

            # speak raw bytes
            streamer.speak(b'abc')

            # speak AudioData
            ad = AudioData(content=b'def', sample_size=2, rate=16000, channels=1)
            streamer.speak(ad)

            # allow the background thread to process
            time.sleep(0.2)

            # terminate and join thread
            streamer.terminate()
        finally:
            pts_mod.Player = orig_player


if __name__ == '__main__':
    unittest.main()

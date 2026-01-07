import queue
import threading
import time
import unittest

from voice_ui.voice_ui import VoiceUI


class FakeTTS:
    def __init__(self):
        self.calls = []

    def speak(self, text, **kwargs):
        self.calls.append((text, kwargs))

    def is_speaking(self):
        return False

    def stop(self):
        pass

    def terminate(self):
        pass


class TestVoiceUITTSThread(unittest.TestCase):
    def test_tts_thread_handles_string_and_tuple_items(self):
        # create a fake `self` object with the attributes the method expects
        class FakeSelf:
            pass

        fake = FakeTTS()
        fs = FakeSelf()
        fs._terminated = False
        fs._speaker_queue = queue.Queue()
        fs._tts_streamer = fake

        # run the unbound function with our fake self in a thread
        t = threading.Thread(
            target=VoiceUI._text_to_speech_thread_function, args=(fs,), daemon=True
        )
        t.start()

        try:
            # string item
            fs._speaker_queue.put("hello")
            time.sleep(0.1)
            self.assertIn(("hello", {}), fake.calls)

            # tuple with None kwargs
            fs._speaker_queue.put(("yo", None))
            time.sleep(0.1)
            self.assertIn(("yo", {}), fake.calls)

            # tuple with invalid kwargs type should be ignored but not raise
            fs._speaker_queue.put(("bad", "notadict"))
            time.sleep(0.1)
        finally:
            fs._terminated = True
            t.join(timeout=1)


if __name__ == "__main__":
    unittest.main()

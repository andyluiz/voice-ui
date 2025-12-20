import os
import struct
import unittest
import wave
from pathlib import Path

import dotenv

from voice_ui.speech_detection.hotword_detector import HotwordDetector

# Load environment variables from .env if present
dotenv.load_dotenv()


def load_wav_to_int16(path: str):
    with wave.open(path, "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()

        if channels != 1 or sampwidth != 2 or framerate != 16000:
            raise ValueError(
                f"WAV file must be mono, 16-bit, 16kHz. Got channels={channels}, sampwidth={sampwidth}, framerate={framerate}"
            )

        frames = wf.getnframes()
        raw = wf.readframes(frames)

    ints = struct.unpack("<" + "h" * (len(raw) // 2), raw)
    return list(ints)


RESOURCE_DIR = Path("tests/resources/hotword")


class IntegratedHotwordDetectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.porcupine_key = os.environ.get("PORCUPINE_ACCESS_KEY")
        cls.resource_map = {
            "hotword_computer_keyword.wav": True,
            "hotword_alexa_keyword.wav": True,
            "hotword_jarvis_keyword.wav": True,
            "hotword_hey_google_keyword.wav": True,
            "hotword_hello_world_keyword.wav": False,
            "hotword_good_computer_keyword.wav": True,
        }

    def setUp(self):
        if not self.porcupine_key:
            self.skipTest(
                "PORCUPINE_ACCESS_KEY not set; skipping Porcupine integration tests"
            )

    def test_list_available_keywords(self):
        detector = HotwordDetector()
        print(f'Available wake words: {", ".join(detector.available_keywords())}')

    def test_hotword_files(self):
        missing = [
            f for f in self.resource_map.keys() if not (RESOURCE_DIR / f).exists()
        ]
        self.assertFalse(missing, f"Missing resource files for hotword test: {missing}")

        for filename, expected in self.resource_map.items():
            with self.subTest(filename=filename):
                path = RESOURCE_DIR / filename
                ints = load_wav_to_int16(str(path))

                detector = HotwordDetector()
                try:
                    chunk_idx = detector.process(ints)
                    detected = chunk_idx >= 0

                    print(f"File {filename} detection={detected} expected={expected}")
                    self.assertEqual(
                        detected,
                        expected,
                        msg=f"File {filename} expected detected={expected} got {detected}",
                    )
                finally:
                    try:
                        del detector
                    except Exception:
                        pass


if __name__ == "__main__":
    unittest.main()

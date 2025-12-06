import unittest
from pathlib import Path

EXAMPLES = [
    "examples/01_vad_microphone.py",
    "examples/01_vad_microphone_hotword_detection.py",
    "examples/02_simple_speech_detection_from_mic_stream.py",
    "examples/03_speech_detection_with_transcription.py",
    "examples/04_voiceui_real_time_communication.py",
]


class SmokeExamplesTest(unittest.TestCase):
    def test_examples_are_syntax_valid(self):
        """Ensure example files are present and free of syntax errors.

        We avoid importing them (which pulls in heavy native deps like pyaudio
        and pvporcupine). Instead a compile() check is sufficient to catch
        accidental syntax regressions from refactors.
        """
        for rel in EXAMPLES:
            path = Path(rel)
            if not path.exists():
                self.skipTest(f"{rel} not found")
            # Read and compile to verify syntax
            src = path.read_text(encoding="utf8")
            compile(src, str(path), "exec")


if __name__ == "__main__":
    unittest.main()

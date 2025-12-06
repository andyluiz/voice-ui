import tempfile
import threading
import unittest
from pathlib import Path

from tests.helpers.audio_utils import (
    FakeMicrophoneVADStream,
    generate_sine_wav,
    inject_minimal_audio_and_hotword_mocks,
)


class AudioPipelineTest(unittest.TestCase):
    def test_speech_detector_processes_wav_via_fake_stream(self):
        # Generate a short WAV file
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "test_tone.wav"
            generate_sine_wav(wav, duration=0.3)

            # Ensure lightweight mocks for native audio/hotword deps are present.
            inject_minimal_audio_and_hotword_mocks()

            # Import speech detector module and patch MicrophoneVADStream
            from voice_ui.speech_detection import speech_detector as sd_mod

            # Prepare event capture
            events = []
            finished = threading.Event()

            def callback(event=None, **kwargs):
                e = event if event is not None else kwargs.get("event")
                events.append(e)
                if e.__class__.__name__ == "SpeechEndedEvent":
                    finished.set()

            original_stream = sd_mod.MicrophoneVADStream

            try:
                def make_fake(*args, **k):
                    return FakeMicrophoneVADStream(wav_path=wav, rate=16000, chunk=800)

                make_fake.DetectionMode = FakeMicrophoneVADStream.DetectionMode
                sd_mod.MicrophoneVADStream = make_fake

                detector = sd_mod.SpeechDetector(on_speech_event=callback, max_speech_duration=5)
                detector.start()

                finished.wait(timeout=5)
                detector.stop()

                names = [e.__class__.__name__ for e in events]
                self.assertIn("SpeechStartedEvent", names)
                self.assertIn("SpeechEndedEvent", names)

            finally:
                sd_mod.MicrophoneVADStream = original_stream


if __name__ == "__main__":
    unittest.main()

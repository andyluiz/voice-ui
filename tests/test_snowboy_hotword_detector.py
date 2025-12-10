import contextlib
import importlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


class TestSnowboyHotwordDetector(unittest.TestCase):
    def test_wait_for_hotword_detected_and_not_detected(self):
        # Build a fake snowboy package to satisfy imports inside the function.
        fake_snowboy = types.ModuleType('snowboy')
        fake_snowboydecoder = types.SimpleNamespace()

        class FakeDetector:
            def __init__(self, *args, **kwargs):
                pass

            def start(self, detected_callback=None, interrupt_check=None, **kwargs):
                if detected_callback:
                    detected_callback()

            def terminate(self):
                pass

        fake_snowboydecoder.HotwordDetector = FakeDetector
        fake_snowboy.snowboydecoder = fake_snowboydecoder

        # Provide lightweight substitutes for voice_ui.alternatives.player and microphone
        sys.modules['voice_ui.alternatives.player'] = types.SimpleNamespace(play_file=lambda *a, **k: None)
        sys.modules['voice_ui.alternatives.microphone'] = types.SimpleNamespace(no_alsa_and_jack_errors=lambda: contextlib.nullcontext())

        with patch.dict(sys.modules, {'snowboy': fake_snowboy}):
            snowboy_mod = importlib.import_module('voice_ui.alternatives.snowboy_hotword_detector')
            with patch.object(snowboy_mod, 'player', new=MagicMock()):
                with patch.object(snowboy_mod, 'no_alsa_and_jack_errors', new=lambda: contextlib.nullcontext()):
                    detected = snowboy_mod.wait_for_hotword(interrupt_check=lambda: False)
                    self.assertTrue(detected)

        # Now simulate no detection
        class FakeDetectorNo:
            def __init__(self, *args, **kwargs):
                pass

            def start(self, detected_callback=None, interrupt_check=None, **kwargs):
                return

            def terminate(self):
                pass

        fake_snowboydecoder.HotwordDetector = FakeDetectorNo
        fake_snowboy.snowboydecoder = fake_snowboydecoder

        with patch.dict(sys.modules, {'snowboy': fake_snowboy}):
            snowboy_mod = importlib.import_module('voice_ui.alternatives.snowboy_hotword_detector')
            with patch.object(snowboy_mod, 'player', new=MagicMock()):
                with patch.object(snowboy_mod, 'no_alsa_and_jack_errors', new=lambda: contextlib.nullcontext()):
                    detected = snowboy_mod.wait_for_hotword(interrupt_check=lambda: True)
                    self.assertFalse(detected)

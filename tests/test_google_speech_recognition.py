import os
import unittest
from unittest.mock import MagicMock, patch

import voice_ui.alternatives.google_speech_recognition as gsr_mod


class TestGoogleSpeechRecognitionListen(unittest.TestCase):
    def test_listen_forwards_languages_and_project(self):
        stub = MagicMock(return_value={"text": "ok"})
        with patch.object(gsr_mod, "google_speech_v2_recognize", new=stub):
            os.environ["GOOGLE_PROJECT_ID"] = "myproj"

            class DummyStream:
                pass

            gsr_mod.listen(DummyStream(), language_codes=["es-ES"])
            self.assertTrue(stub.called)

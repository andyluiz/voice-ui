import unittest

from voice_ui.speech_recognition import SpeechToTextTranscriber, TranscriberFactory
from voice_ui.speech_synthesis import TextToSpeechAudioStreamer, TTSFactory


class DummyTranscriber(SpeechToTextTranscriber):
    NAME = "DummyTranscriberForTest"

    @classmethod
    def name(cls):
        return cls.NAME

    def transcribe(self, audio_data, prompt=''):
        return f"transcribed:{audio_data}"


class DummyTTS(TextToSpeechAudioStreamer):
    NAME = "DummyTTSForTest"

    @classmethod
    def name(cls):
        return cls.NAME

    def speak(self, text, voice=None):
        # simple no-op implementation for tests
        self._last = (text, voice)

    def terminate(self):
        pass

    def speech_queue_size(self) -> int:
        return 0

    def is_speaking(self):
        return False

    def stop(self):
        self._stopped = True

    def is_stopped(self):
        return getattr(self, "_stopped", False)

    def available_voices(self):
        return []


class TestTranscriberFactory(unittest.TestCase):
    def setUp(self):
        # Ensure a clean state for our test name
        try:
            TranscriberFactory.unregister_transcriber(DummyTranscriber.NAME)
        except KeyError:
            pass

    def tearDown(self):
        try:
            TranscriberFactory.unregister_transcriber(DummyTranscriber.NAME)
        except KeyError:
            pass

    def test_register_create_and_unregister(self):
        TranscriberFactory.register_transcriber(DummyTranscriber.NAME, DummyTranscriber)

        inst = TranscriberFactory.create(DummyTranscriber.NAME)
        self.assertIsInstance(inst, SpeechToTextTranscriber)
        self.assertEqual(inst.transcribe('audio123'), 'transcribed:audio123')

        # Unregister and ensure creation now fails
        TranscriberFactory.unregister_transcriber(DummyTranscriber.NAME)
        with self.assertRaises(RuntimeError):
            TranscriberFactory.create(DummyTranscriber.NAME)


class TestTTSFactory(unittest.TestCase):
    def setUp(self):
        try:
            TTSFactory.unregister_tts(DummyTTS.NAME)
        except KeyError:
            pass

    def tearDown(self):
        try:
            TTSFactory.unregister_tts(DummyTTS.NAME)
        except KeyError:
            pass

    def test_register_create_and_unregister(self):
        TTSFactory.register_tts(DummyTTS.NAME, DummyTTS)

        inst = TTSFactory.create(DummyTTS.NAME)
        self.assertIsInstance(inst, TextToSpeechAudioStreamer)
        inst.speak('hello', voice='v1')
        self.assertEqual(inst._last, ('hello', 'v1'))

        TTSFactory.unregister_tts(DummyTTS.NAME)
        with self.assertRaises(RuntimeError):
            TTSFactory.create(DummyTTS.NAME)


if __name__ == '__main__':
    unittest.main()

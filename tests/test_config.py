import unittest

import voice_ui.config as config_mod


class TestConfig(unittest.TestCase):
    def test_defaults_and_path_conversion(self):
        c = config_mod.VoiceUIConfig()
        self.assertEqual(c.speech_detection.vad_engine, "SileroVAD")

        c2 = config_mod.VoiceUIConfig(
            speech_detection=config_mod.SpeechDetectionConfig(
                voice_profiles_dir=str("/tmp")
            )
        )
        self.assertTrue(hasattr(c2.speech_detection.voice_profiles_dir, "joinpath"))

    def test_invalid_threshold_raises(self):
        with self.assertRaises(ValueError):
            config_mod.SpeechDetectionConfig(vad_threshold=2.0)

    def test_negative_durations_raise(self):
        with self.assertRaises(ValueError):
            config_mod.SpeechDetectionConfig(pre_speech_duration=-1)
        with self.assertRaises(ValueError):
            config_mod.SpeechDetectionConfig(post_speech_duration=-1)

    def test_invalid_max_speech_duration(self):
        with self.assertRaises(ValueError):
            config_mod.SpeechDetectionConfig(max_speech_duration=0)

    def test_invalid_hotword_timeout(self):
        with self.assertRaises(ValueError):
            config_mod.SpeechDetectionConfig(hotword_inactivity_timeout=0)

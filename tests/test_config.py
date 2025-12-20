import unittest

import voice_ui.config as config_mod


class TestConfig(unittest.TestCase):
    def test_defaults_and_path_conversion(self):
        c = config_mod.VoiceUIConfig()
        self.assertEqual(c.vad_engine, "SileroVAD")

        c2 = config_mod.VoiceUIConfig(voice_profiles_dir=str("/tmp"))
        self.assertTrue(hasattr(c2.voice_profiles_dir, "joinpath"))

    def test_invalid_threshold_raises(self):
        with self.assertRaises(ValueError):
            config_mod.VoiceUIConfig(vad_threshold=2.0)

    def test_negative_durations_raise(self):
        with self.assertRaises(ValueError):
            config_mod.VoiceUIConfig(pre_speech_duration=-1)
        with self.assertRaises(ValueError):
            config_mod.VoiceUIConfig(post_speech_duration=-1)

    def test_invalid_max_speech_duration(self):
        with self.assertRaises(ValueError):
            config_mod.VoiceUIConfig(max_speech_duration=0)

    def test_invalid_hotword_timeout(self):
        with self.assertRaises(ValueError):
            config_mod.VoiceUIConfig(hotword_inactivity_timeout=0)

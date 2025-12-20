import unittest
from unittest.mock import MagicMock

from voice_ui.voice_activity_detection.vad_factory import VADFactory
from voice_ui.voice_activity_detection.vad_i import IVoiceActivityDetector


class TestVADFactory(unittest.TestCase):

    def setUp(self):
        # Reset the vad_classes dictionary before each test
        VADFactory.vad_classes = {}

    def test_register_vad(self):
        mock_vad_class = MagicMock(spec=IVoiceActivityDetector)
        VADFactory.register_vad("mock_vad", mock_vad_class)
        self.assertIn("mock_vad", VADFactory.vad_classes)
        self.assertIs(VADFactory.vad_classes["mock_vad"], mock_vad_class)

    def test_create_valid_vad(self):
        mock_vad_class = MagicMock(spec=IVoiceActivityDetector)
        mock_instance = mock_vad_class.return_value
        VADFactory.register_vad("mock_vad", mock_vad_class)
        instance = VADFactory.create("mock_vad", some_arg="test")
        mock_vad_class.assert_called_with(some_arg="test")
        self.assertIs(instance, mock_instance)

    def test_create_invalid_vad(self):
        with self.assertRaises(ValueError) as context:
            VADFactory.create("invalid_vad")
        self.assertEqual(str(context.exception), "Invalid VAD type: invalid_vad")

    def test_unregister_vad(self):
        mock_vad_class = MagicMock(spec=IVoiceActivityDetector)
        VADFactory.register_vad("mock_vad", mock_vad_class)
        VADFactory.unregister_vad("mock_vad")
        self.assertNotIn("mock_vad", VADFactory.vad_classes)

    def test_unregister_nonexistent_vad(self):
        with self.assertRaises(KeyError) as context:
            VADFactory.unregister_vad("nonexistent_vad")
        self.assertEqual(
            str(context.exception), "'VAD type not found: nonexistent_vad'"
        )


if __name__ == "__main__":
    unittest.main()

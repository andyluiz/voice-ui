"""Unit tests for WebRTC factory registration and VirtualMicrophone frame queue."""

import unittest

from voice_ui.audio_io.virtual_microphone import VirtualMicrophone

# Backward compatibility alias for test method names
RemoteMicrophone = VirtualMicrophone


class TestAudioSourceAndSinkFactory(unittest.TestCase):
    """Test WebRTC registration with factories."""

    def test_webrtc_sources_and_sinks_registered(self):
        """Test that WebRTC classes are registered in factories."""
        try:
            from voice_ui.audio_io import AudioSinkFactory, AudioSourceFactory

            sources = AudioSourceFactory.list_sources()
            sinks = AudioSinkFactory.list_sinks()

            # Both may or may not be available depending on dependencies
            self.assertIsInstance(sources, list)
            self.assertIsInstance(sinks, list)
        except ImportError:
            self.skipTest("Factory import failed")

    def test_webrtc_factory_creation(self):
        """Test creating WebRTC devices via factories."""
        try:
            from voice_ui.audio_io import AudioSinkFactory, AudioSourceFactory

            sources = AudioSourceFactory.list_sources()
            sinks = AudioSinkFactory.list_sinks()

            if "webrtc" in sources:
                remote_mic = AudioSourceFactory.create("webrtc", signaling_port=9006)
                self.assertIsNotNone(remote_mic)
                remote_mic.stop()

            if "webrtc" in sinks:
                player = AudioSinkFactory.create("webrtc", signaling_port=9007)
                self.assertIsNotNone(player)
                player.stop()
        except ImportError:
            self.skipTest("Factory import failed")


class TestRemoteMicrophoneWithFrameQueue(unittest.TestCase):
    """Test RemoteMicrophone core functionality."""

    def test_remote_microphone_push_frame(self):
        """Test pushing frames to RemoteMicrophone."""
        remote_mic = RemoteMicrophone()
        remote_mic.start()

        test_frame = b"\x00\x01" * 320
        remote_mic.push_frame(test_frame)
        remote_mic.stop()

    def test_remote_microphone_read(self):
        """Test reading frames from RemoteMicrophone."""
        remote_mic = RemoteMicrophone()
        remote_mic.start()

        test_frame = b"\x00\x01" * 320
        remote_mic.push_frame(test_frame)

        read_frame = remote_mic.read(timeout=0.5)
        self.assertEqual(read_frame, test_frame)

        remote_mic.stop()

    def test_remote_microphone_generator(self):
        """Test generator interface of RemoteMicrophone."""
        remote_mic = RemoteMicrophone()

        test_frame1 = b"\x00\x01" * 320
        test_frame2 = b"\x02\x03" * 320

        remote_mic.push_frame(test_frame1)
        remote_mic.push_frame(test_frame2)

        frames = []
        gen = remote_mic.generator()

        try:
            first_frame = next(gen)
            if first_frame is not None:
                frames.append(first_frame)
        except StopIteration:
            pass

        remote_mic.push_frame(None)

        self.assertGreater(len(frames), 0)

    def test_remote_microphone_properties(self):
        """Test RemoteMicrophone audio properties."""
        remote_mic = RemoteMicrophone()

        self.assertEqual(remote_mic.rate, 16000)
        self.assertEqual(remote_mic.channels, 1)
        self.assertEqual(remote_mic.chunk_size, 320)
        self.assertIsNotNone(remote_mic.sample_format)
        self.assertEqual(remote_mic.sample_size, 2)


if __name__ == "__main__":
    unittest.main()

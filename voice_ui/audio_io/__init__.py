"""Audio I/O module for Voice UI.

This module provides audio input/output abstractions including:
- Microphone capture
- Audio player/speaker output
- Remote audio sources and sinks (WebRTC)
- Audio data structures
"""

# Import core classes for public API
from .audio_data import AudioData
from .audio_sink_factory import AudioSinkFactory
from .audio_source_factory import AudioSourceFactory
from .microphone import MicrophoneStream
from .player import Player
from .queued_player import QueuedAudioPlayer
from .virtual_microphone import VirtualMicrophone
from .virtual_player import VirtualPlayer

# Register WebRTC sources and sinks if available
try:
    from .webrtc_remote_microphone import WebRTCRemoteMicrophone

    AudioSourceFactory.register_source("webrtc", WebRTCRemoteMicrophone)
    __webrtc_microphone_available = True
except ImportError:
    __webrtc_microphone_available = False

try:
    from .webrtc_remote_player import WebRTCRemotePlayer

    AudioSinkFactory.register_sink("webrtc", WebRTCRemotePlayer)
    __webrtc_player_available = True
except ImportError:
    __webrtc_player_available = False

# Try to import WebRTCSignalingServer for convenience
try:
    from .webrtc_signaling_server import WebRTCSignalingServer  # noqa: F401

    __webrtc_signaling_available = True
except ImportError:
    __webrtc_signaling_available = False

__all__ = [
    "AudioData",
    "AudioSourceFactory",
    "AudioSinkFactory",
    "MicrophoneStream",
    "Player",
    "QueuedAudioPlayer",
    "VirtualMicrophone",
    "VirtualPlayer",
]

# Add WebRTC classes to public API if available
if (
    __webrtc_microphone_available
    or __webrtc_player_available
    or __webrtc_signaling_available
):
    __all__.extend(
        [
            "WebRTCSignalingServer",
            "WebRTCRemoteMicrophone",
            "WebRTCRemotePlayer",
        ]
    )

"""Speech synthesis package public API.

This package re-exports the factory ``create_tts_streamer`` and the base
``TextToSpeechAudioStreamer`` class to provide a convenient package-level
API surface::

    from voice_ui.speech_synthesis import create_tts_streamer

Keep the factory implementation in ``text_to_speech_streamer_factory.py`` to
avoid eager or circular imports; this file only exposes the public symbols.
"""

from .text_to_speech_streamer_factory import create_tts_streamer
from .text_to_speech_streamer import TextToSpeechAudioStreamer

__all__ = ["create_tts_streamer", "TextToSpeechAudioStreamer"]


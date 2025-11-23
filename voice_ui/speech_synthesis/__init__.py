"""Speech synthesis package public API.

This package exposes the class-based ``TTSFactory`` for creating and
managing text-to-speech streamer backends at runtime. Use::

    from voice_ui.speech_synthesis import TTSFactory

to create or register TTS backends. The previous functional factory has been
removed in favor of the class-based API which makes registration and
thread-safety explicit.

Keep the factory implementation in ``text_to_speech_streamer_factory.py`` to
avoid eager or circular imports; this file only exposes the public symbols.
"""

from .text_to_speech_streamer import TextToSpeechAudioStreamer
from .text_to_speech_streamer_factory import TTSFactory

__all__ = ["TextToSpeechAudioStreamer", "TTSFactory"]

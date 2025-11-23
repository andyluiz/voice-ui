"""Speech recognition package public API.

This package exposes the class-based `TranscriberFactory` for creating and
managing speech-to-text transcribers at runtime. Use

  from voice_ui.speech_recognition import TranscriberFactory

to create or register transcribers. The old functional factory has been
removed in favor of the class-based API to make registration and
thread-safety explicit.

Keep the factory implementation in `speech_to_text_transcriber_factory.py`
to avoid eager or circular imports; this file only provides a package-level
friendly API surface.
"""

from .speech_to_text_transcriber import SpeechToTextTranscriber
from .speech_to_text_transcriber_factory import TranscriberFactory

__all__ = ["SpeechToTextTranscriber", "TranscriberFactory"]

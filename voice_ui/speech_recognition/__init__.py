"""Speech recognition package public API.

This package re-exports the convenient factory `create_transcriber` so callers
can do::

	from voice_ui.speech_recognition import create_transcriber

Keep the factory implementation in `speech_to_text_transcriber_factory.py`
to avoid eager or circular imports; this file only provides a package-level
friendly API surface.
"""

from .speech_to_text_transcriber import SpeechToTextTranscriber
from .speech_to_text_transcriber_factory import create_transcriber

__all__ = ["create_transcriber", "SpeechToTextTranscriber"]

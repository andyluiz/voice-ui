"""
Configuration classes for voice_ui components.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


@dataclass
class VoiceUIConfig:
    """
    Configuration for the VoiceUI class.

    This replaces the loose dictionary-based configuration with a typed,
    documented configuration class that provides:
    - Type safety and IDE autocomplete
    - Clear documentation of all available settings
    - Default values in one place
    - Validation of configuration parameters

    Attributes:
        vad_engine: Voice Activity Detection engine to use.
            Supported values: 'SileroVAD', 'FunASRVAD', 'PicoVoiceVAD'
            Default: 'SileroVAD'

        vad_threshold: VAD confidence threshold (0.0 to 1.0).
            Higher values reduce false positives but may miss quiet speech.
            Default: 0.5

        pre_speech_duration: Seconds of audio to include before detected speech.
            Should be >= 0.75 to avoid truncating hotword detection.
            Default: 1.0

        post_speech_duration: Seconds of audio to include after speech ends.
            Default: 1.0

        max_speech_duration: Maximum duration (seconds) for a single speech segment.
            Longer segments are truncated.
            Default: 10

        voice_profiles_dir: Directory path containing speaker profile files for
            speaker identification. If None, speaker identification is disabled.
            Default: None

        additional_keyword_paths: Dictionary mapping hotword/keyword names to
            custom keyword file paths. Used for hotword detection beyond default.
            Default: {}

        audio_transcriber: Speech-to-text engine factory name.
            Supported values: 'whisper', 'local-whisper'
            Default: 'whisper'

        tts_engine: Text-to-speech engine factory name.
            Supported values: 'openai-tts', 'google', 'passthrough'
            Default: 'openai-tts'

        voice_name: Voice identifier/name for TTS output.
            Available voices depend on the TTS engine selected.
            Default: None (uses engine default)

        hotword_inactivity_timeout: Seconds of inactivity before automatically
            switching back to hotword detection mode. If None, inactivity timeout
            is disabled.
            Default: None
    """

    vad_engine: str = "SileroVAD"
    vad_threshold: float = 0.5
    pre_speech_duration: float = 1.0
    post_speech_duration: float = 1.0
    max_speech_duration: int = 10
    voice_profiles_dir: Optional[Path] = None
    additional_keyword_paths: Dict[str, str] = field(default_factory=dict)
    audio_transcriber: str = "whisper"
    tts_engine: str = "openai-tts"
    voice_name: Optional[str] = None
    hotword_inactivity_timeout: Optional[float] = None

    def __post_init__(self):
        """Validate configuration parameters after initialization."""
        # Convert string paths to Path objects if needed
        if isinstance(self.voice_profiles_dir, str):
            self.voice_profiles_dir = Path(self.voice_profiles_dir)

        # Validate threshold range
        if not 0.0 <= self.vad_threshold <= 1.0:
            raise ValueError(
                f"vad_threshold must be between 0.0 and 1.0, got {self.vad_threshold}"
            )

        # Validate durations are non-negative
        if self.pre_speech_duration < 0:
            raise ValueError(
                f"pre_speech_duration must be non-negative, got {self.pre_speech_duration}"
            )

        if self.post_speech_duration < 0:
            raise ValueError(
                f"post_speech_duration must be non-negative, got {self.post_speech_duration}"
            )

        if self.max_speech_duration <= 0:
            raise ValueError(
                f"max_speech_duration must be positive, got {self.max_speech_duration}"
            )

        # Validate hotword inactivity timeout if specified
        if (
            self.hotword_inactivity_timeout is not None
            and self.hotword_inactivity_timeout <= 0
        ):
            raise ValueError(
                f"hotword_inactivity_timeout must be positive or None, got {self.hotword_inactivity_timeout}"
            )

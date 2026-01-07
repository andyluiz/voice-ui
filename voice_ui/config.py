"""
Configuration classes for voice_ui components.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from voice_ui.audio_io.audio_sink import AudioSink
from voice_ui.audio_io.audio_source import AudioSource


@dataclass
class SpeechDetectionConfig:
    """
    Configuration for speech detection (VAD + hotword detection).

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
    hotword_inactivity_timeout: Optional[float] = None

    def __post_init__(self):
        """Validate speech detection configuration parameters."""
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


@dataclass
class TranscriptionConfig:
    """
    Configuration for speech-to-text transcription.

    Attributes:
        engine: Speech-to-text engine factory name.
            Supported values: 'whisper', 'local-whisper'
            Default: 'whisper'
    """

    engine: str = "whisper"


@dataclass
class TextToSpeechConfig:
    """
    Configuration for text-to-speech synthesis.

    Attributes:
        engine: Text-to-speech engine factory name.
            Supported values: 'openai-tts', 'google', 'passthrough'
            Default: 'openai-tts'
    """

    engine: str = "openai-tts"


@dataclass
class AudioIOConfig:
    """
    Configuration for audio input/output.

    Attributes:
        audio_source_instance: Custom audio source instance to use instead of default microphone.
            Default: None

        audio_sink_instance: Custom audio sink/player instance to use instead of default speaker output.
            Default: None
    """

    audio_source_instance: Optional[AudioSource] = None
    audio_sink_instance: Optional[AudioSink] = None

    def __post_init__(self):
        """Validate audio I/O configuration parameters."""
        if not isinstance(self.audio_source_instance, (AudioSource, type(None))):
            raise ValueError(
                f"audio_source_instance must be an instance of AudioSource or None, got {type(self.audio_source_instance)}"
            )

        if not isinstance(self.audio_sink_instance, (AudioSink, type(None))):
            raise ValueError(
                f"audio_sink_instance must be an instance of AudioSink or None, got {type(self.audio_sink_instance)}"
            )


@dataclass
class VoiceUIConfig:
    """
    Configuration for the VoiceUI class.

    This configuration uses nested dataclasses to organize settings by component:
    - Type safety and IDE autocomplete
    - Clear documentation of all available settings
    - Organized by functional area (SpeechDetection, Transcription, TTS, AudioIO)
    - Validation of configuration parameters

    Attributes:
        speech_detection: Configuration for speech detection (VAD + hotword).
        transcription: Configuration for speech-to-text transcription.
        text_to_speech: Configuration for text-to-speech synthesis.
        audio_io: Configuration for audio input/output.
    """

    speech_detection: SpeechDetectionConfig = field(
        default_factory=SpeechDetectionConfig
    )
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    text_to_speech: TextToSpeechConfig = field(default_factory=TextToSpeechConfig)
    audio_io: AudioIOConfig = field(default_factory=AudioIOConfig)

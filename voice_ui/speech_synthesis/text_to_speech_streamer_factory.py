import logging

from .pass_through_text_to_speech_streamer import PassThroughTextToSpeechAudioStreamer
from .text_to_speech_streamer import TextToSpeechAudioStreamer

logger = logging.getLogger(__name__)

available_tts_engines = [
    PassThroughTextToSpeechAudioStreamer,
]

try:
    from .google_text_to_speech_streamer import GoogleTextToSpeechAudioStreamer

    # Module loaded successfully
    available_tts_engines.append(GoogleTextToSpeechAudioStreamer)
except ModuleNotFoundError:
    pass

try:
    from .openai_text_to_speech_streamer import OpenAITextToSpeechAudioStreamer

    # Module loaded successfully
    available_tts_engines.append(OpenAITextToSpeechAudioStreamer)
except ModuleNotFoundError:
    pass


def create_tts_streamer(tts_engine_name) -> TextToSpeechAudioStreamer:
    logger.info(f"Creating TTS streamer for '{tts_engine_name}'")

    for tts_engine in available_tts_engines:
        if tts_engine_name == tts_engine.name():
            return tts_engine()

    raise RuntimeError(f"Engine '{tts_engine_name}' is not available")

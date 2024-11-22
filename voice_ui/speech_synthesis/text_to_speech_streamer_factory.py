from .text_to_speech_streamer import TextToSpeechAudioStreamer

available_tts_engines = []

try:
    from .google_text_to_speech_streamer import GoogleTextToSpeechAudioStreamer

    # Module loaded successfully
    available_tts_engines.append(GoogleTextToSpeechAudioStreamer)
except ModuleNotFoundError:
    pass

try:
    from .whisper_text_to_speech_streamer import WhisperTextToSpeechAudioStreamer

    # Module loaded successfully
    available_tts_engines.append(WhisperTextToSpeechAudioStreamer)
except ModuleNotFoundError:
    pass


def create_tts_streamer(tts_engine_name) -> TextToSpeechAudioStreamer:
    for tts_engine in available_tts_engines:
        if tts_engine_name == tts_engine.name():
            return tts_engine()

    raise RuntimeError(f"Engine '{tts_engine_name}' is not available")

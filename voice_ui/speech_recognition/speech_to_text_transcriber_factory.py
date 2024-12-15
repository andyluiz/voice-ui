from .speech_to_text_transcriber import SpeechToTextTranscriber

available_transcription_engines = []

# try:
#     from .google_speech_recognition import GoogleSpeechToTextTranscriber

#     # Module loaded successfully
#     available_transcription_engines.append(GoogleSpeechToTextTranscriber)
# except ModuleNotFoundError:
#     pass

try:
    from .openai_local_whisper import LocalWhisperTranscriber

    # Module loaded successfully
    available_transcription_engines.append(LocalWhisperTranscriber)
except ModuleNotFoundError:
    pass

try:
    from .openai_whisper import WhisperTranscriber

    # Module loaded successfully
    available_transcription_engines.append(WhisperTranscriber)
except ModuleNotFoundError:
    pass


def create_transcriber(transcription_engine_name) -> SpeechToTextTranscriber:
    if transcription_engine_name is None:
        return None

    for engine in available_transcription_engines:
        if transcription_engine_name == engine.name():
            return engine()

    raise RuntimeError(f"Engine '{transcription_engine_name}' is not available")

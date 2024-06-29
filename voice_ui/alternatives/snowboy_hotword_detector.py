import logging

from . import player
from .microphone import no_alsa_and_jack_errors


def wait_for_hotword(
    # detected_callback,
    decoder_model="src/resources/snowboy_models/computer.umdl",
    sensitivity=0.6,
    audio_gain=1,
    apply_frontend=True,
    interrupt_check=lambda: False,
    **kwargs
):
    from snowboy import snowboydecoder

    logging.info('Waiting for hotword')

    # Play the OK file
    player.play_file('src/resources/sounds/voiceinput3.wav')

    detected = False

    def detected_callback():
        nonlocal detected
        detected = True
        detector.terminate()

    detector = snowboydecoder.HotwordDetector(
        decoder_model=decoder_model,
        sensitivity=sensitivity,
        audio_gain=audio_gain,
        # apply_frontend=apply_frontend,
    )

    with no_alsa_and_jack_errors():
        detector.start(
            detected_callback=detected_callback,
            interrupt_check=interrupt_check,
            **kwargs
        )

    if detected:
        logging.info('Hotword was detected')

        # Play the voice input started
        player.play_file('src/resources/sounds/voiceinput4.wav')
    else:
        logging.info('Hotword not detected')

    return detected

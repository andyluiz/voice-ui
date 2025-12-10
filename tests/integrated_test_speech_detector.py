# import logging
import unittest
import wave

import dotenv
from six.moves import queue

from voice_ui.speech_detection.speech_detector import (
    MetaDataEvent,
    PartialSpeechEndedEvent,
    SpeechDetector,
    SpeechEndedEvent,
    SpeechStartedEvent,
)
from voice_ui.speech_recognition import TranscriberFactory


class TestSpeechDetector(unittest.TestCase):

    def setUp(self):
        dotenv.load_dotenv()

        # logging.basicConfig(
        #     level=logging.DEBUG,
        #     handlers=[
        #         logging.StreamHandler(),
        #     ]
        # )

        self.transcriber = TranscriberFactory.create("whisper")

    def test_get_chunk_from_buffer_with_non_empty_queue(self):
        transcriptions = []

        events = queue.Queue()

        def process_event():
            # Wait for the next event
            event = events.get(timeout=1)
            audio_data = event.get('audio_data')
            metadata = event.get('metadata')

            if isinstance(event, SpeechStartedEvent):
                print('\nSpeech start detected')

            elif isinstance(event, (SpeechEndedEvent, PartialSpeechEndedEvent)):
                print('\nSpeech {} detected'.format("end" if isinstance(event, SpeechEndedEvent) else "partial end"))

                print(f"Speaker: {metadata['speaker']}")

                response = self.transcriber.transcribe(
                    audio_data=audio_data,
                    prompt=transcriptions[-1] if isinstance(event, PartialSpeechEndedEvent) and transcriptions else None,
                )

                # Response is already a string from the transcriber
                if isinstance(response, str):
                    transcription = response
                else:
                    # Fallback in case response has a .text attribute
                    transcription = response.text

                # print(response)
                if isinstance(event, SpeechEndedEvent) or len(transcriptions) == 0:
                    transcriptions.append(transcription)
                    print(transcription, end='\n\n')
                else:
                    transcriptions[-1] += ' ' + transcription
                    print(transcription)
                # print('\n'.join(last_transcription))
            elif isinstance(event, MetaDataEvent):
                max_size = len('Voice Probability: {}'.format(100 * '#'))
                print(
                    ' ' * max_size + '\rVoice Probability: {}'.format(int(metadata['voice_probability'] * 100) * '#'),
                    end="\r",
                    flush=True,
                )
                pass
            else:
                raise Exception("Unknown event: {}".format(event))

        self.speech_detector = SpeechDetector(
            on_speech_event=lambda event: events.put(event),
            post_speech_duration=1.0,
            # max_speech_duration=10,
            # speaker_profiles_dir=(config.user_data_dir / 'voice_profiles'),
        )

        #############################################################################
        # Read audio from file
        with wave.open("tests/resources/youtube_show.wav", "rb") as wf:
            int16_list = wf.readframes(wf.getnframes())
            for i in range(0, len(int16_list), 1024):
                chunks = int16_list[i:i + 1024]
                if len(chunks) == 1024:
                    self.speech_detector._source_stream._buff.put(chunks)
        #############################################################################

        # Detect speech
        self.speech_detector.start()

        # Give the detector thread time to process all audio and events
        import time
        max_wait = 30  # Wait up to 30 seconds for processing
        start_time = time.time()

        try:
            while time.time() - start_time < max_wait:
                try:
                    process_event()
                except queue.Empty:
                    # Check if detector thread is still alive
                    if not self.speech_detector._thread.is_alive():
                        # Thread finished, try to process remaining events
                        while not events.empty():
                            try:
                                process_event()
                            except queue.Empty:
                                break
                        break
                    # Thread still alive, keep waiting
                    time.sleep(0.1)
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            self.speech_detector.stop()

        # Assert
        # Print actual transcriptions for debugging
        print(f"\nActual transcriptions count: {len(transcriptions)}")
        for i, t in enumerate(transcriptions):
            print(f"Transcription {i}: {t[:100]}...")

        # Check that we got some transcriptions
        self.assertGreater(len(transcriptions), 0, "No transcriptions were generated")


if __name__ == '__main__':
    unittest.main()

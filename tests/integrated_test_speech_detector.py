# import logging
import os
import unittest
import wave
from datetime import datetime

import alsaaudio
import dotenv
import openai
from six.moves import queue
from voice_ui.speech_recognition.speech_detector import (
    MetaDataEvent,
    PartialSpeechEndedEvent,
    SpeechDetector,
    SpeechEndedEvent,
    SpeechStartedEvent,
)


class TestSpeechDetector(unittest.TestCase):

    def setUp(self):
        dotenv.load_dotenv()

        # logging.basicConfig(
        #     level=logging.DEBUG,
        #     handlers=[
        #         logging.StreamHandler(),
        #     ]
        # )

        self.client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        self.mixer = alsaaudio.Mixer()   # defined alsaaudio.Mixer to change volume
        current_volume = self.mixer.getvolume()  # get volume float value
        print(f"Initial Volume: {current_volume}")

    def test_get_chunk_from_buffer_with_non_empty_queue(self):
        transcriptions = []

        events = queue.Queue()

        def process_event():
            global current_volume

            # Wait for the next event
            event = events.get(timeout=1)
            audio_data = event.get('audio_data')
            metadata = event.get('metadata')

            if isinstance(event, SpeechStartedEvent):
                print('\nSpeech start detected')
                current_volume = self.mixer.getvolume()  # get volume float value
                # print(f"Current Volume: {current_volume}")
                self.mixer.setvolume(30, channel=alsaaudio.MIXER_CHANNEL_ALL)  # set volume

            elif isinstance(event, (SpeechEndedEvent, PartialSpeechEndedEvent)):
                print('\nSpeech {} detected'.format("end" if isinstance(event, SpeechEndedEvent) else "partial end"))
                if isinstance(event, SpeechEndedEvent):
                    for c, v in enumerate(current_volume):
                        self.mixer.setvolume(v, channel=c)  # set original volume

                print(f"Speaker: {metadata['speaker']}")

                # Create the name of the audio file using current time
                now = datetime.now()
                audio_file_name = "speech_" + now.strftime("%Y%m%d-%H%M%S") + ".wav"

                with wave.open(audio_file_name, "wb") as wf:
                    wf.setnchannels(audio_data['channels'])
                    wf.setsampwidth(audio_data['sample_size'])
                    wf.setframerate(audio_data['rate'])
                    wf.writeframes(audio_data['content'])
                    wf.close()

                with open(audio_file_name, "rb") as audio_file:
                    response = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        # language="pt",
                        prompt=transcriptions[-1] if isinstance(event, PartialSpeechEndedEvent) and transcriptions else None,
                        response_format="verbose_json",
                    )

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
            pv_access_key=os.environ['PORCUPINE_ACCESS_KEY'],
            callback=lambda event: events.put(event),
            post_speech_duration=1.0,
            # max_speech_duration=10,
            # speaker_profiles_dir=(config.user_data_dir / 'voice_profiles'),
        )

        # #############################################################################
        # # Read audio from file
        # with wave.open("tests/resources/youtube_show.wav", "rb") as wf:
        #     source_data = queue.Queue()
        #     int16_list = wf.readframes(wf.getnframes())
        #     for i in range(0, len(int16_list), 1024):
        #         chunks = int16_list[i:i + 1024]
        #         if len(chunks) == 1024:
        #             source_data.put(chunks)

        # def get_chunks_from_file(*args, **kwargs):
        #     return source_data.get()

        # # Replace function _get_chunk_from_buffer
        # self.speech_detector._get_chunk_from_buffer = get_chunks_from_file
        # #############################################################################

        # Detect speech
        self.speech_detector.start()

        try:
            while True:
                process_event()
        except queue.Empty:
            pass
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            self.speech_detector.stop()

        # Assert
        self.assertEqual(
            transcriptions,
            [
                """Incogni for supporting PBS. Hey everyone, just letting you know that there's new limited edition merch at the merch store. More info at the end of the episode. May 8th, 2024, on the blazing surface of the sun, a collection of sunspots have been growing for days. Ignored by most of us, but watched with fascination and some confusion. These dark spots marked the presence of an invisible tangle of magnetic fields that held an enormous magnetic energy. Energy that would be released in a series of eruptions sending blasts of plasma and magnetic field directly at the Earth. Two days later, this coronal mass ejection plowed into Earth's own magnetic field, causing auroras that were visible in the tropics. I was in upstate New York, and the entire northern sky was ablaze, albeit dimly. And the sun is only getting started. Solar activity is still increasing in a sunspot cycle.""",
                """that is proving way more intense than scientists predicted, just how much stronger is it going to get? The Great Big Storm back in May was the strongest experience by the Earth since 1989, and we're still at least a few months from the peak of activity of the current 11-year solar cycle. Which is weird, because this, the 25th cycle since sunspot monitoring began, was supposed to be a particularly weak one. In fact, the strength of the solar cycles had been decreasing for decades. Instead though, the Sun's activity this cycle is rising far more rapidly than predicted towards an imminent polarity reversal of the Sun's entire magnetic field. So what's going on? Why does the Sun's magnetic field act like this? Why does it act so crazy, and why is it acting so unpredictably crazy right now, and how much more crazy is it going to get? To answer these excellent questions, we're going to have to first ask some more basic questions. Like, what is the source of the Sun's magnetic field? Why does solar activity change over an 11-year cycle, and what causes the magnetic field to flip direction, resetting this cycle? And how can we even predict the strength of a solar cycle in advance? First though, a quick 101 on solar structure. The Sun's interior has three main parts. The core, where hydrogen is fused into helium, a process that produces all of the Sun's energy. Then you have the radiative zone, where fusion power is transported upwards by high-energy photons bouncing their way through the depths. Finally, you have the convective zone, where energy is transported by flows of plasma carrying heat up to the surface. The core and the radiative zone are fluids, but they rotate like solid spheres with all latitudes, completing a rotation in the same amount of time. But the convective zone is much more sloshy and fluid-like. Over most of the top 30% of the solar radius, the equatorial material rotates once per 25 days,"""
            ],
        )


if __name__ == '__main__':
    unittest.main()

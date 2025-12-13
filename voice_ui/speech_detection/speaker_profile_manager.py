import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

import pveagle
import pvrecorder

DEFAULT_DEVICE_INDEX = -1

logger = logging.getLogger(__name__)


class SpeakerProfileManager:
    def __init__(self, profile_dir: Path):
        self._profile_dir = profile_dir
        self._eagle_recognizer = None

        if not self._profile_dir.exists():
            raise FileNotFoundError(
                f"Voice profile directory '{self._profile_dir}' does not exist"
            )

        # Load existing profiles
        self.load_profiles()

    def __del__(self):
        if self._eagle_recognizer:
            self._eagle_recognizer.delete()

    def create_profile(self, profile_name: str):
        profile_path = self._profile_dir / f"{profile_name}.bin"
        if profile_path.exists():
            raise FileExistsError(f"Profile '{profile_name}' already exists")

        eagle_profiler = pveagle.create_profiler(
            access_key=os.environ["PORCUPINE_ACCESS_KEY"]
        )

        print("Starting recorder. Please speak to enroll the profile")
        try:
            enroll_recorder = pvrecorder.PvRecorder(
                device_index=DEFAULT_DEVICE_INDEX,
                frame_length=eagle_profiler.min_enroll_samples,
            )
            enroll_recorder.start()

            enroll_percentage = 0.0
            while True:
                try:
                    if enroll_percentage < 100.0:
                        print(
                            f"Enroll percentage: {enroll_percentage}. Continue speaking..."
                        )
                    else:
                        print(
                            "Enrolling is complete. Continue speaking to improve quality or press Ctrl+C to stop"
                        )
                    audio_frame = enroll_recorder.read()
                    enroll_percentage, feedback = eagle_profiler.enroll(audio_frame)
                except KeyboardInterrupt:
                    break

            print("Enrolling is complete. Stopping recorder")
            enroll_recorder.stop()
        finally:
            if enroll_recorder is not None:
                enroll_recorder.delete()

        speaker_profile_data = eagle_profiler.export()

        with open(profile_path, "wb") as f:
            f.write(speaker_profile_data.to_bytes())

        eagle_profiler.delete()

    @property
    def profiles(self):
        return [profile["name"] for profile in self._speaker_profiles]

    def load_profiles(self):
        logger.info(f"Loading speaker profiles from {self._profile_dir}")
        profiles = []
        for file in self._profile_dir.glob("*.bin"):
            with open(file.absolute(), "rb") as f:
                profiles.append(
                    {
                        "name": file.stem,
                        "profile_data": pveagle.EagleProfile.from_bytes(f.read()),
                    }
                )

        logger.info(f"Loaded {len(profiles)} speaker profiles")
        self._speaker_profiles = profiles

        if self._eagle_recognizer:
            self._eagle_recognizer.delete()
            self._eagle_recognizer = None

        self._eagle_recognizer = pveagle.create_recognizer(
            access_key=os.environ["PORCUPINE_ACCESS_KEY"],
            speaker_profiles=list(
                map(lambda x: x["profile_data"], self._speaker_profiles)
            ),
        )

    def detect_speaker(self, audio_frames: List[float]) -> Optional[List[float]]:
        if self._eagle_recognizer is None:
            logger.error("Eagle recognizer is not initialized")
            return None

        # Split the audio frames into chunks of frame_length
        scores = []
        for i in range(0, len(audio_frames), self._eagle_recognizer.frame_length):
            audio_frame = audio_frames[i : i + self._eagle_recognizer.frame_length]

            if self._eagle_recognizer.frame_length != len(audio_frame):
                continue

            frame_scores = self._eagle_recognizer.process(audio_frame)
            if frame_scores:
                scores.append(frame_scores)

        # Calculate the average scores for each speaker
        scores = [sum(s) / len(s) for s in zip(*scores)]

        if not scores:
            logger.debug("No speaker detected")
            return None

        return scores

    def get_speaker_name(self, scores: List[float]) -> Optional[Tuple[str, int, float]]:
        if not scores:
            return None

        # Find the speaker by returning the index of the one with the highest score
        speaker_id, score = max(enumerate(scores), key=lambda x: x[1])
        if score < 0.2:
            return None

        speaker_name = self.profiles[speaker_id]

        return {
            "name": speaker_name,
            "id": speaker_id,
            "score": score,
        }

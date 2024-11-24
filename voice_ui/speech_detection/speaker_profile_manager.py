import os
from pathlib import Path
from typing import List

import pveagle
import pvrecorder

DEFAULT_DEVICE_INDEX = -1


class SpeakerProfileManager:
    def __init__(self, profile_dir: Path):
        self._profile_dir = profile_dir
        if not self._profile_dir.exists():
            raise ValueError(f"Profile directory '{self._profile_dir}' does not exist")

    def create_profile(self, profile_name: str):
        profile_path = self._profile_dir / f"{profile_name}.bin"
        if profile_path.exists():
            raise FileExistsError(f"Profile '{profile_name}' already exists")

        eagle_profiler = pveagle.create_profiler(access_key=os.environ["PORCUPINE_ACCESS_KEY"])

        print("Starting recorder. Please speak to enroll the profile")
        try:
            enroll_recorder = pvrecorder.PvRecorder(device_index=DEFAULT_DEVICE_INDEX, frame_length=eagle_profiler.min_enroll_samples)
            enroll_recorder.start()

            enroll_percentage = 0.0
            while True:
                try:
                    if enroll_percentage < 100.0:
                        print(f"Enroll percentage: {enroll_percentage}. Continue speaking...")
                    else:
                        print("Enrolling is complete. Continue speaking to improve quality or press Ctrl+C to stop")
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

    def list_profiles(self):
        profiles = [file.stem for file in self._profile_dir.glob("*.bin")]
        return profiles

    def load_profiles(self) -> List[dict]:
        if not self._profile_dir.exists():
            raise FileNotFoundError(f"Voice profile directory '{self._profile_dir}' does not exist")

        profiles = []
        for file in self._profile_dir.glob("*.bin"):
            with open(file.absolute(), "rb") as f:
                profiles.append(
                    {
                        'name': file.stem,
                        'profile_data': pveagle.EagleProfile.from_bytes(f.read())
                    }
                )

        return profiles

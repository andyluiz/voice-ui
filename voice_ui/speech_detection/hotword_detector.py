import logging
import os
from typing import Dict

import pvporcupine

logger = logging.getLogger(__name__)


class HotwordDetector:
    def __init__(
        self,
        keywords=None,
        sensitivities=None,
        additional_keyword_paths: Dict[str, str] = {},
    ):
        self._additional_keyword_paths = additional_keyword_paths

        if keywords is None:
            keywords = self.available_keywords()

        KEYWORD_PATHS = self.available_keyword_paths()
        selected_keyword_paths = [KEYWORD_PATHS[x] for x in keywords]

        logger.info("Hotwords: {}".format(", ".join(keywords)))

        # Initialize Porcupine with the specified keyword file
        self._handle = pvporcupine.create(
            access_key=os.environ["PORCUPINE_ACCESS_KEY"],
            # model_path=os.path.abspath('src/resources/porcupine/porcupine_params_pt.pv'),
            keyword_paths=selected_keyword_paths,
            # keywords=keywords,
            sensitivities=sensitivities,
        )

    def __del__(self):
        self._handle.delete()

    def available_keyword_paths(self):
        keyword_paths = pvporcupine.KEYWORD_PATHS

        if self._additional_keyword_paths:
            for keyword, path in self._additional_keyword_paths.items():
                if not os.path.exists(path):
                    raise ValueError(f"Keyword path {path} does not exist")

                keyword_paths[keyword] = os.path.abspath(path)

        return keyword_paths

    def available_keywords(self):
        return self.available_keyword_paths().keys()

    def process(self, audio_frames):
        # Split the audio frames into chunks of frame_length
        for i in range(0, len(audio_frames), self._handle.frame_length):
            audio_frame = audio_frames[i : i + self._handle.frame_length]

            if self._handle.frame_length != len(audio_frame):
                continue

            result = self._handle.process(audio_frame)
            if result >= 0:
                return result

        return -1

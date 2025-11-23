# TODO

## Hotword detections

- Move HotwordDetector class to its own file
- Define the return type of the `process()` function.
  - Suggestions:
    - the name of the detected keyword
    - a probability array of each keyword
- Implement interface and factory for hotword detectors

## Voice Profile manager

- Implement interface and factory for profile managers
- Implement new speaker identifiers

## Testing

- Create functional tests to check VAD, Speech Synthesis, and Speech Detection and Recognition.

## Others

- Create a configuration class for VoiceUI to replace the dictionary.
  - The dictionary is too loose and don't explicitly specify the available settings and their defaults
  - Implement a read-config-from-file functionality

- Update diagram
- Create documentation

import pyaudio
from six.moves import queue

from .audio_source import AudioSource
from .pyaudio_load_message_suppressor import no_alsa_and_jack_errors

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 20)  # 50ms


class MicrophoneStream(AudioSource):
    """Opens a recording stream as a generator yielding audio chunks."""

    def __init__(self, rate: int = RATE, chunk: int = CHUNK) -> None:
        # Backing attributes for AudioSourceBase interface
        self._rate = rate
        self._chunk = chunk
        self._channels = 1
        self._sample_format = pyaudio.paInt16
        self._sample_size = 2
        self._max_bytes_per_yield = 25000

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self._closed = True

        with no_alsa_and_jack_errors():
            self._audio_interface = pyaudio.PyAudio()

        self._audio_stream = self._audio_interface.open(
            format=self._sample_format,
            channels=self._channels,
            rate=self._rate,
            input=True,
            frames_per_buffer=self._chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
            start=False,  # Do not start the stream immediately
        )

        # Backing attributes `_channels`, `_rate`, `_chunk`, `_sample_format`,
        # and `_sample_size` implement the AudioSourceBase contract.

    # AudioSourceBase interface -------------------------------------------------
    @property
    def channels(self) -> int:
        return self._channels

    @property
    def rate(self) -> int:
        return self._rate

    @property
    def chunk_size(self) -> int:
        return self._chunk

    @property
    def sample_format(self):
        return self._sample_format

    @property
    def sample_size(self) -> int:
        try:
            return self._audio_interface.get_sample_size(self._sample_format)
        except Exception:
            return self._sample_size

    def __enter__(self):
        self.resume()

        return self

    def __exit__(self, type, value, traceback):
        self.pause()
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def pause(self) -> None:
        self._audio_stream.stop_stream()
        self._closed = True

    def resume(self) -> None:
        self._closed = False
        self._audio_stream.start_stream()

    @staticmethod
    def _yield_bytes(data: bytes, byte_limit: int):
        # Check if the data is of type 'bytes'. If not, raise an AssertionError.
        assert isinstance(data, bytes)

        # Loop through the data by chunks of size 'byte_limit'
        for i in range(0, len(data), byte_limit):
            # Yield a slice of the data from index 'i' up to but not including 'i + byte_limit'.
            # This will return control back to the caller of this function, allowing it to process
            # the yielded bytes before resuming this function for the next iteration.
            yield data[i : (i + byte_limit)]

    def generator(self):
        # Keep running this loop until the stream is closed
        while not self._closed:
            # Get the next chunk of data from the buffer. This call will block (i.e., wait)
            # if there's no data available.
            # If the chunk is None, this indicates the end of the audio stream, and we stop iteration.
            chunk = self._buff.get()
            if chunk is None:
                return
            # Start building a list of data with the first chunk
            data = [chunk]

            # Now we try to get all remaining chunks of data from the buffer.
            while True:
                try:
                    # Try to get the next chunk of data from the buffer without blocking.
                    # If no data is available, an Empty exception will be raised and we break the loop.
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    # Add the chunk to our data list
                    data.append(chunk)
                except queue.Empty:
                    # If there's no more data in the buffer, break the loop
                    break

            # Yield the data as bytes, up to the maximum number of bytes per yield.
            # This will return control back to the caller of this function, allowing it to process
            # the yielded bytes before resuming this function for the next iteration.
            yield from self._yield_bytes(b"".join(data), self._max_bytes_per_yield)

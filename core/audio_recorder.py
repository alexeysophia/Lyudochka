"""Audio recording via sounddevice (PortAudio)."""
import tempfile
import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

_SAMPLE_RATE = 16000
_CHANNELS = 1
_DTYPE = "int16"


class AudioRecorder:
    """Records audio from the default microphone into a temp WAV file."""

    def __init__(self) -> None:
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._temp_path: str | None = None

    def start(self) -> None:
        """Open microphone stream and start accumulating frames."""
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=_SAMPLE_RATE,
            channels=_CHANNELS,
            dtype=_DTYPE,
            callback=self._callback,
        )
        self._stream.start()

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time: object,
        status: sd.CallbackFlags,
    ) -> None:
        with self._lock:
            self._frames.append(indata.copy())

    def stop(self) -> Path:
        """Stop recording and save to a temporary WAV file. Returns the file path."""
        self._close_stream()
        audio_data = self._collect_audio()
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self._temp_path = tmp.name
        tmp.close()
        with wave.open(self._temp_path, "wb") as wf:
            wf.setnchannels(_CHANNELS)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(_SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())
        return Path(self._temp_path)

    def cancel(self) -> None:
        """Stop recording and discard the audio."""
        self._close_stream()
        if self._temp_path:
            Path(self._temp_path).unlink(missing_ok=True)
            self._temp_path = None

    def _close_stream(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def _collect_audio(self) -> np.ndarray:
        with self._lock:
            frames = list(self._frames)
        if frames:
            return np.concatenate(frames, axis=0)
        return np.zeros((0, _CHANNELS), dtype=_DTYPE)

from __future__ import annotations

import io
import threading
import wave
from typing import Optional, List

import numpy as np
import sounddevice as sd


class AudioRecorder:
    """
    Records mono 16kHz 16-bit PCM into WAV bytes.
    Provides VU level via get_level() in [0..1].
    """

    def __init__(self, samplerate: int = 16000, channels: int = 1):
        self.samplerate = samplerate
        self.channels = channels
        self.dtype = "int16"
        self._stream: Optional[sd.InputStream] = None
        self._frames: List[np.ndarray] = []
        self._lock = threading.Lock()
        self._level = 0.0

    def _callback(self, indata, frames, time_info, status):
        if status:
            # Dropouts etc. are ignored here
            pass
        # indata dtype may differ; ensure int16
        data = indata.copy()
        if data.dtype != np.int16:
            # Convert to int16 range
            if np.issubdtype(data.dtype, np.floating):
                data = (np.clip(data, -1.0, 1.0) * 32767).astype(np.int16)
            else:
                data = data.astype(np.int16)
        with self._lock:
            self._frames.append(data)
            # update level (peak)
            peak = float(np.max(np.abs(data.astype(np.int32)))) / 32768.0
            self._level = peak

    def start(self) -> None:
        if self._stream is not None:
            return
        self._frames = []
        self._level = 0.0
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            dtype=self.dtype,
            callback=self._callback,
        )
        try:
            self._stream.start()
        except Exception:
            self._stream.close()
            self._stream = None
            raise

    def stop(self) -> bytes:
        if self._stream is None:
            return b""
        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None
        with self._lock:
            frames = self._frames
            self._frames = []

        if not frames:
            return b""
        pcm = np.concatenate(frames, axis=0)
        raw = pcm.tobytes(order="C")
        # Wrap to WAV
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.samplerate)
            wf.writeframes(raw)
        return buf.getvalue()

    def get_level(self) -> float:
        return float(self._level)


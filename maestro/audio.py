"""Audio loading, validation, and preprocessing.

Reads WAV / MP3 / FLAC / M4A into the internal AudioData representation.
Performs mono down-mix, DC removal, peak normalization, and silence trimming.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, Union

import numpy as np
from scipy.signal import resample_poly

from .config import AppConfig
from .errors import ErrorCode, MaestroError
from .models import AudioData

SUPPORTED_FORMATS = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}


class AudioLoader:
    """Loads and validates audio files."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def load(self, path: Union[str, Path, io.BytesIO]) -> AudioData:
        """Load path (or in-memory bytes stream) into internal audio."""
        if isinstance(path, (str, Path)):
            return self._load_file(Path(path))
        return self._load_stream(path)

    def _load_file(self, path: Path) -> AudioData:
        if not path.exists():
            raise MaestroError(ErrorCode.INVALID_AUDIO, f"Audio file not found: {path}")
        fmt = path.suffix.lower()
        if fmt not in SUPPORTED_FORMATS:
            raise MaestroError(
                ErrorCode.UNSUPPORTED_FORMAT,
                f"Unsupported format '{fmt}'. Supported: {sorted(SUPPORTED_FORMATS)}",
                details={"format": fmt},
            )
        if path.stat().st_size == 0:
            raise MaestroError(ErrorCode.AUDIO_EMPTY, f"Audio file is empty: {path}")
        try:
            with open(path, "rb") as fh:
                return self._decode(fh, str(path))
        except (EOFError, RuntimeError, OSError, ValueError) as exc:
            raise MaestroError(
                ErrorCode.INVALID_AUDIO,
                f"Failed to decode audio file: {exc}",
                details={"path": str(path)},
            ) from exc

    def _load_stream(self, stream: io.BytesIO) -> AudioData:
        stream.seek(0)
        data = stream.read()
        if not data:
            raise MaestroError(ErrorCode.AUDIO_EMPTY, "Uploaded audio is empty")
        try:
            return self._decode(io.BytesIO(data), "upload")
        except (EOFError, RuntimeError, OSError, ValueError) as exc:
            raise MaestroError(
                ErrorCode.INVALID_AUDIO,
                f"Failed to decode uploaded audio: {exc}",
            ) from exc

    def _decode(self, fileobj, name: str) -> AudioData:
        samples = None
        sr = None
        try:
            import soundfile as sf

            info = sf.info(fileobj)
            fileobj.seek(0)
            samples, sr = sf.read(fileobj, dtype="float32", always_2d=True)
        except Exception:
            samples, sr = self._decode_librosa(fileobj)
        if samples is None or samples.size == 0:
            raise MaestroError(ErrorCode.AUDIO_EMPTY, f"Decoded audio is empty: {name}")

        channels = samples.shape[1] if samples.ndim == 2 else 1
        original_sr = sr

        if sr != self.config.sample_rate:
            samples = self._resample(samples, sr, self.config.sample_rate)
            sr = self.config.sample_rate

        duration = samples.shape[0] / sr
        self._validate_duration(duration, name)

        return AudioData(
            samples=samples.astype(np.float32),
            sample_rate=sr,
            path=name if name != "upload" else None,
            original_sample_rate=original_sr,
            channels_at_load=channels,
            duration=duration,
        )

    def _decode_librosa(self, fileobj) -> tuple[np.ndarray, int]:
        fileobj.seek(0)
        try:
            import librosa

            y, sr = librosa.load(fileobj, sr=None, mono=True)
            return np.expand_dims(y, axis=1), sr
        except Exception as exc:
            raise MaestroError(
                ErrorCode.INVALID_AUDIO,
                f"Could not decode audio (soundfile + librosa failed): {exc}",
            ) from exc

    @staticmethod
    def _resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
        if sr_in == sr_out:
            return x
        gcd = int(np.gcd(sr_in, sr_out))
        return resample_poly(x, sr_out // gcd, sr_in // gcd, axis=0)

    def _validate_duration(self, duration: float, name: str) -> None:
        if duration < self.config.min_duration_seconds:
            raise MaestroError(
                ErrorCode.AUDIO_TOO_SHORT,
                f"Audio is too short ({duration:.3f}s, min "
                f"{self.config.min_duration_seconds}s): {name}",
                details={"duration": duration},
            )
        if duration > self.config.max_duration_seconds:
            raise MaestroError(
                ErrorCode.AUDIO_TOO_LONG,
                f"Audio exceeds max duration ({duration:.1f}s > "
                f"{self.config.max_duration_seconds}s): {name}",
                details={"duration": duration},
            )


class AudioPreprocessor:
    """Mono down-mix, DC removal, normalization, silence trimming."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def process(self, audio: AudioData) -> AudioData:
        mono = self.to_mono(audio.samples)
        mono = self.remove_dc(mono)
        if self.config.trim_silence:
            mono = self.trim_edges(mono, audio.sample_rate)
        mono = self.normalize(mono, self.config.amp_normalize_peak)
        return AudioData(
            samples=mono,
            sample_rate=audio.sample_rate,
            path=audio.path,
            original_sample_rate=audio.original_sample_rate,
            channels_at_load=audio.channels_at_load,
        )

    @staticmethod
    def to_mono(x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64)
        if x.ndim == 2:
            return x.mean(axis=1)
        return x

    @staticmethod
    def remove_dc(x: np.ndarray) -> np.ndarray:
        if x.size == 0:
            return x
        return x - float(x.mean())

    def trim_edges(self, x: np.ndarray, sr: int) -> np.ndarray:
        if x.size == 0:
            return x
        hop = 512
        frames = len(x) // hop
        if frames == 0:
            return x
        rms_blocks = np.sqrt(
            (x[: frames * hop].reshape(frames, hop) ** 2).mean(axis=1)
        )
        threshold = 10.0 ** (self.config.silence_threshold_db / 20.0)
        nonsilent = np.flatnonzero(rms_blocks >= threshold)
        if nonsilent.size == 0:
            return x
        start = max(0, nonsilent[0] - 1) * hop
        end = min(len(x), (nonsilent[-1] + 2) * hop)
        return x[start:end]

    @staticmethod
    def normalize(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
        m = float(np.max(np.abs(x))) if x.size else 0.0
        if m < 1e-9:
            return np.asarray(x, dtype=np.float64)
        out = x * (peak / m)
        return np.clip(out, -1.0, 1.0)

    def frame_rms_db(self, x: np.ndarray, sr: int, hop: int) -> np.ndarray:
        frames = len(x) // hop
        if frames == 0:
            return np.array([], dtype=np.float64)
        rms = np.sqrt((x[: frames * hop].reshape(frames, hop) ** 2).mean(axis=1))
        rms = np.maximum(rms, 1e-9)
        return 20.0 * np.log10(rms)

"""Automatic lyric transcription (speech-to-text) for the vocal track.

Wraps ``faster-whisper`` so the engine can generate lyrics directly from the
isolated vocals — no manual lyric text required. Lazily loads the CTranslate2
model and caches it across requests (like the Demucs separator).
"""

from __future__ import annotations

import logging
import threading

import numpy as np

from .config import AppConfig
from .errors import ErrorCode, MaestroError, wrap_exception
from .models import AudioData

logger = logging.getLogger("maestro.lyric_asr")

_MODEL_LOCK = threading.Lock()
_MODEL_CACHE: dict[tuple[str, str, str], object] = {}


def _shared_model(model_name: str, device: str, compute_type: str):
    """Load (and cache) the faster-whisper model keyed by its settings."""
    key = (model_name, device, compute_type)
    if key in _MODEL_CACHE:
        return _MODEL_CACHE[key]
    with _MODEL_LOCK:
        if key in _MODEL_CACHE:
            return _MODEL_CACHE[key]
        logger.info("Loading faster-whisper model '%s' (%s, %s)...", model_name, device, compute_type)
        try:
            from faster_whisper import WhisperModel

            model = WhisperModel(model_name, device=device, compute_type=compute_type)
        except Exception as exc:
            raise MaestroError(
                ErrorCode.LYRICS_ALIGNMENT_FAILED,
                f"Could not load lyric transcription model '{model_name}': {exc}",
            ) from exc
        _MODEL_CACHE[key] = model
        logger.info("Loaded faster-whisper model '%s'", model_name)
        return model


class WhisperLyricGenerator:
    """Transcribe an audio track into lyric text using faster-whisper."""

    def __init__(self, model_name: str = "small", device: str = "cpu", compute_type: str = "int8") -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type

    @staticmethod
    def _resolve_device(requested: str) -> str:
        if requested in ("cpu", "cuda"):
            return requested
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def _load_model(self):
        return _shared_model(self.model_name, self.device, self.compute_type)

    @staticmethod
    def _to_16k(audio: AudioData) -> np.ndarray:
        samples = np.asarray(audio.mono(), dtype=np.float32)
        if audio.sample_rate == 16000:
            return samples
        from scipy.signal import resample_poly

        gcd = int(np.gcd(int(audio.sample_rate), 16000))
        return resample_poly(samples, 16000 // gcd, int(audio.sample_rate) // gcd).astype(np.float32)

    def transcribe(self, audio: AudioData) -> str:
        """Return the lyric text transcribed from *audio*, or "" if empty."""
        if not audio.samples.size:
            raise MaestroError(ErrorCode.LYRICS_ALIGNMENT_FAILED, "cannot transcribe lyrics: empty audio")
        samples = self._to_16k(audio)
        model = self._load_model()
        try:
            segments, _ = model.transcribe(
                samples,
                language=None,
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300},
                condition_on_previous_text=True,
            )
            parts: list[str] = []
            for seg in segments:
                text = (seg.text or "").strip()
                if text:
                    parts.append(text)
            return " ".join(parts)
        except Exception as exc:
            raise MaestroError(
                ErrorCode.LYRICS_ALIGNMENT_FAILED,
                "automatic lyric transcription failed",
                details=wrap_exception(exc, ErrorCode.LYRICS_ALIGNMENT_FAILED, "transcribe").message,
            ) from exc


def generate_lyrics(audio: AudioData, conf: AppConfig) -> str:
    """Convenience: generate lyric text for the vocal track, or "" when ASR is off."""
    model_name = (conf.lyric_asr_model or "").strip().lower()
    if not model_name or model_name in ("none", "off", "disabled"):
        return ""
    generator = WhisperLyricGenerator(model_name=model_name, device=conf.device, compute_type="int8")
    return generator.transcribe(audio)
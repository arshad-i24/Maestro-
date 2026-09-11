"""Vocal separation (source separation).

Demucs (htdemucs) as primary isolate-vocals engine.

Design rules:
* Swappable behind BaseSeparator interface.
* Lazy loading + model caching across requests.
* If Demucs (torch) unavailable → explicit error unless passthrough is opted in.
"""

from __future__ import annotations

import logging
import tempfile
import threading
from pathlib import Path
from typing import Optional

import numpy as np

from .config import AppConfig
from .errors import ErrorCode, MaestroError, wrap_exception
from .models import AudioData, SeparationResult

logger = logging.getLogger("maestro.separation")

_MODEL_LOCK = threading.Lock()
_CACHE_LOCK = threading.Lock()
_SEPARATOR_CACHE: dict[str, Optional["BaseSeparator"]] = {}


class BaseSeparator:
    """Interface all separation backends implement."""

    method = "abstract"

    def separate(self, audio: AudioData) -> SeparationResult:
        raise NotImplementedError

    @property
    def available(self) -> bool:
        return True


class PassthroughSeparator(BaseSeparator):
    """No real separation: returns the mix as the 'vocal' stem."""

    method = "passthrough"

    def separate(self, audio: AudioData) -> SeparationResult:
        return SeparationResult(
            vocals=audio,
            method=self.method,
            separated=False,
        )


class DemucsSeparator(BaseSeparator):
    """Demucs-based vocal isolation (htdemucs default model)."""

    method = "demucs"

    def __init__(
        self,
        model_name: str = "htdemucs",
        device: str = "cpu",
        model_dir: str = "",
        reuse: bool = True,
        sample_rate: int = 22050,
    ) -> None:
        self.model_name = model_name
        self.device = self._resolve_device(device)
        self.model_dir = model_dir
        self.reuse = reuse
        self.sample_rate = sample_rate
        self._model = None
        self._model_id: tuple = ()
        if model_dir:
            Path(model_dir).mkdir(parents=True, exist_ok=True)

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
        if not self.reuse:
            return self._build_model()
        with _MODEL_LOCK:
            if self._model is not None:
                return self._model
            logger.info("Loading demucs model '%s' on %s ...", self.model_name, self.device)
            self._model = self._build_model()
            logger.info("Loaded demucs model '%s'", self.model_name)
            return self._model

    def _build_model(self):
        try:
            from demucs.pretrained import get_model

            kwargs = {}
            if self.model_dir:
                kwargs["repo"] = Path(self.model_dir)
            model = get_model(name=self.model_name, **kwargs)
            import torch

            if self.device == "cuda" and torch.cuda.is_available():
                model.cuda()
            else:
                model.cpu()
            model.eval()
            return model
        except Exception as exc:
            raise MaestroError(
                ErrorCode.VOCAL_SEPARATION_FAILED,
                f"Could not load demucs model '{self.model_name}': {exc}",
            ) from exc

    def separate(self, audio: AudioData) -> SeparationResult:
        if not self.available:
            raise MaestroError(
                ErrorCode.VOCAL_SEPARATION_FAILED,
                "Demucs separator unavailable (torch/demucs not installed). Set vocal_separation_model='passthrough' to use full mix explicitly.",
            )
        try:
            return self._run(audio)
        except MaestroError:
            raise
        except Exception as exc:
            raise MaestroError(
                ErrorCode.VOCAL_SEPARATION_FAILED,
                "Demucs separation failed",
                details=wrap_exception(exc, ErrorCode.VOCAL_SEPARATION_FAILED, "run").message,
            ) from exc

    def _run(self, audio: AudioData) -> SeparationResult:
        import torch
        from demucs.apply import apply_model

        model = self._load_model()
        # Demucs expects audio at the model's native sample rate (typically
        # 44100 Hz). Our engine works at conf.sample_rate (22050 Hz), so the
        # mix must be up-sampled first — otherwise apply_model hears the track
        # time-compressed and every separated stem comes back shorter than the
        # input, losing the tail of the song.
        mix = np.asarray(audio.mono(), dtype=np.float32)
        mix = self._resample(mix, self.sample_rate, int(model.samplerate))
        mix = torch.tensor(mix)
        mix = torch.stack([mix, mix], dim=0)
        mix = mix.unsqueeze(0)
        device = next(model.parameters()).device
        mix = mix.to(device).requires_grad_(False)
        with torch.no_grad():
            out = apply_model(model, mix, device=device, shifts=0, split=True, progress=False)

        sources = list(getattr(model, "sources", []))
        try:
            vocal_idx = sources.index("vocals")
        except ValueError:
            vocal_idx = 0

        separated = out[0].mean(dim=1).cpu().numpy().astype(np.float32)
        vocals = separated[vocal_idx]
        mix_mono = mix[0].mean(dim=0).cpu().numpy().astype(np.float32)
        instrumental = mix_mono - vocals

        vocals = self._resample(vocals, int(model.samplerate), self.sample_rate)
        instrumental = self._resample(instrumental, int(model.samplerate), self.sample_rate)

        voices = AudioData(vocals, self.sample_rate)
        instr = AudioData(instrumental, self.sample_rate)
        return SeparationResult(
            vocals=voices,
            instrumental=instr,
            method=self.method,
            model=self.model_name,
            device=self.device,
            separated=True,
        )

    @staticmethod
    def _resample(x: np.ndarray, sr_in: float, sr_out: int) -> np.ndarray:
        from scipy.signal import resample_poly

        if int(sr_in) == sr_out:
            return x
        gcd = int(np.gcd(int(sr_in), sr_out))
        return resample_poly(x, sr_out // gcd, int(sr_in) // gcd).astype(np.float32)

    @property
    def available(self) -> bool:
        try:
            import demucs
            import torch
            return True
        except Exception:
            return False


def _make_separator(conf: AppConfig) -> BaseSeparator:
    requested = conf.vocal_separation_model.lower()
    if requested in ("none", "passthrough", "skip"):
        return PassthroughSeparator()
    return DemucsSeparator(
        model_name=requested,
        device=conf.device,
        model_dir=conf.model_dir,
        reuse=conf.reuse_models,
        sample_rate=conf.sample_rate,
    )


def get_separator(conf: AppConfig) -> BaseSeparator:
    """Return a cached separator instance (models persist across requests)."""
    key = f"{conf.vocal_separation_model}|{conf.device}|{conf.sample_rate}|{conf.reuse_models}"
    with _CACHE_LOCK:
        if key not in _SEPARATOR_CACHE:
            _SEPARATOR_CACHE[key] = _make_separator(conf)
        return _SEPARATOR_CACHE[key]


def separate_vocals(
    audio: AudioData,
    conf: AppConfig,
    output_dir: str = "",
    keep_stems: bool = False,
) -> tuple[SeparationResult, list[str]]:
    """Separate vocals from audio. Returns (result, warnings).
    
    Raises MaestroError if separation is requested but unavailable/failed.
    Use vocal_separation_model='passthrough' in config to explicitly opt-in to full-mix mode.
    """
    warnings: list[str] = []
    separator = get_separator(conf)
    result = separator.separate(audio)

    # Compute diagnostics for the vocal stem
    vocal_rms = float(np.sqrt(np.mean(result.vocals.mono() ** 2))) if result.vocals.samples.size > 0 else 0.0
    vocal_peak = float(np.max(np.abs(result.vocals.mono()))) if result.vocals.samples.size > 0 else 0.0
    vocal_duration = result.vocals.duration

    instrumental_rms = 0.0
    if result.instrumental is not None and result.instrumental.samples.size > 0:
        instrumental_rms = float(np.sqrt(np.mean(result.instrumental.mono() ** 2)))

    # Attach diagnostics to result for pipeline/API exposure
    result.vocal_rms = vocal_rms
    result.vocal_peak = vocal_peak
    result.vocal_duration = vocal_duration
    result.instrumental_rms = instrumental_rms

    if result.separated and (keep_stems or output_dir):
        base_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="maestro_stems_"))
        base_dir.mkdir(parents=True, exist_ok=True)
        stem = "audio"
        try:
            import soundfile as sf

            vocals_path = base_dir / f"{stem}_vocals.wav"
            instr_path = base_dir / f"{stem}_instrumental.wav"
            sf.write(vocals_path, result.vocals.mono(), result.vocals.sample_rate)
            sf.write(instr_path, result.instrumental.mono(), result.instrumental.sample_rate)
            result.vocals_path = str(vocals_path)
            result.instrumental_path = str(instr_path)
        except Exception as exc:
            logger.warning("Could not persist stems: %s", exc)
            if not output_dir:
                try:
                    base_dir.rmdir()
                except OSError:
                    pass

    # Add diagnostic warning if vocal energy is very low
    if vocal_rms < 0.001:
        warnings.append(
            f"WARNING: Separated vocal stem has very low energy (RMS={vocal_rms:.6f}). "
            "Pitch detection may be unreliable. Check vocal separation quality."
        )

    return result, warnings

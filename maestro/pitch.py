"""Pitch detection and note segmentation.

Pitch detection: frame-level fundamental frequency estimation using
pYIN (default), STFT (fallback), or combined.

Note segmentation: converts continuous pitch frames into discrete musical
notes while filtering vibrato artifacts and merging adjacent same-pitch notes.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

from .config import AppConfig
from .errors import ErrorCode, MaestroError, wrap_exception
from .models import AudioData, DetectedNote, PitchFrame

logger = logging.getLogger("maestro.pitch")


# ---------------------------------------------------------------------------
# Pitch Detection
# ---------------------------------------------------------------------------


class BasePitchDetector(ABC):
    """Interface for frame-level f0 estimators."""

    @abstractmethod
    def detect(self, audio: AudioData) -> list[PitchFrame]:
        """Return one frame per hop step covering the whole input."""


class PyinDetector(BasePitchDetector):
    method = "pyin"

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def detect(self, audio: AudioData) -> list[PitchFrame]:
        try:
            import librosa

            y = np.asarray(audio.mono(), dtype=np.float64)
            result = librosa.pyin(
                y,
                fmin=self.config.fmin_hz,
                fmax=self.config.fmax_hz,
                sr=audio.sample_rate,
                frame_length=self.config.frame_length,
                hop_length=self.config.hop_length,
            )
            if hasattr(result, "frequencies"):
                f0 = np.asarray(result.frequencies)
                voiced = np.asarray(result.voiced_flag)
                prob = np.asarray(result.voiced_probability)
            else:
                f0, voiced, prob = result
        except (ImportError, ValueError, RuntimeError) as exc:
            raise MaestroError(
                ErrorCode.PITCH_DETECTION_FAILED,
                "pyin pitch detection failed",
                details=wrap_exception(exc, ErrorCode.PITCH_DETECTION_FAILED, "pyin").message,
            ) from exc

        hop = self.config.hop_length
        times = (np.arange(len(f0)) * hop) / audio.sample_rate
        frames: list[PitchFrame] = []
        for t, freq, is_voiced, p in zip(times, f0, voiced, prob):
            freq = float(freq) if np.isfinite(freq) else None
            voiced_flag = bool(is_voiced) and freq is not None
            conf = float(p)
            if not voiced_flag:
                conf = 0.0
            midi = _freq_to_midi(freq) if freq is not None else None
            frames.append(
                PitchFrame(
                    time=float(t),
                    frequency=freq,
                    voiced=voiced_flag,
                    confidence=conf,
                    midi_note=midi,
                )
            )
        return frames


class StftDetector(BasePitchDetector):
    """Lightweight spectral-peak detector (fallback / experimental)."""

    method = "stft"

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def detect(self, audio: AudioData) -> list[PitchFrame]:
        y = np.asarray(audio.mono(), dtype=np.float64)
        sr = audio.sample_rate
        n_fft = self.config.frame_length
        hop = self.config.hop_length
        if len(y) < n_fft:
            return []
        n_frames = (len(y) - n_fft) // hop + 1
        window = np.hanning(n_fft)
        freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
        band = (freqs >= self.config.fmin_hz) & (freqs <= self.config.fmax_hz)
        frames: list[PitchFrame] = []
        energies = []
        for i in range(n_frames):
            seg = y[i * hop : i * hop + n_fft] * window
            spec = np.abs(np.fft.rfft(seg))
            energies.append(float(np.sum(spec) / n_fft + 1e-12))
        energy_floor = float(np.mean(energies)) * 0.1 if energies else 1.0
        for i in range(n_frames):
            seg = y[i * hop : i * hop + n_fft] * window
            spec = np.abs(np.fft.rfft(seg))
            energy = float(np.sum(spec) / n_fft + 1e-12)
            silenced = energy < energy_floor
            sub = np.where(band, spec, 0.0)
            peak_bin = int(np.argmax(sub))
            peak_mag = float(sub[peak_bin])
            if peak_mag <= 0 or silenced:
                frames.append(PitchFrame(time=i * hop / sr, frequency=None, voiced=False, confidence=0.0))
                continue
            freq = float(freqs[peak_bin])
            conf = min(1.0, 20.0 * np.log10(peak_mag + 1e-9) / 20.0 + 0.5)
            conf = float(np.clip(conf, 0.0, 1.0))
            frames.append(
                PitchFrame(
                    time=i * hop / sr,
                    frequency=freq,
                    voiced=True,
                    confidence=conf,
                    midi_note=_freq_to_midi(freq),
                )
            )
        return frames


class CombinedDetector(BasePitchDetector):
    """Pyin primary, STFT fallback if pyin's library is missing."""

    method = "combined"

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._primary: BasePitchDetector = PyinDetector(config)

    def detect(self, audio: AudioData) -> list[PitchFrame]:
        try:
            return self._primary.detect(audio)
        except MaestroError:
            if isinstance(self._primary, PyinDetector):
                logger.warning("pyin unavailable; falling back to stft detector")
                return StftDetector(self.config).detect(audio)
            raise


def create_pitch_detector(method: str, config: AppConfig) -> BasePitchDetector:
    method = (method or config.pitch_detection_method).lower()
    if method == "stft":
        return StftDetector(config)
    if method == "combined":
        return CombinedDetector(config)
    return PyinDetector(config)


# ---------------------------------------------------------------------------
# Note Segmentation
# ---------------------------------------------------------------------------


def _median_smooth(freqs: list[float], window: int) -> list[float]:
    if window <= 1 or not freqs:
        return freqs
    out = [float(f) for f in freqs]
    w = max(1, window // 2)
    n = len(freqs)
    for i in range(n):
        lo, hi = max(0, i - w), min(n, i + w + 1)
        out[i] = float(np.median(freqs[lo:hi]))
    return out


def _semitone_distance(left_midi: float, right_midi: float) -> float:
    return abs(left_midi - right_midi)


def _merge_adjacent(notes: list[DetectedNote], tolerance: float, max_gap: float) -> list[DetectedNote]:
    if len(notes) < 2:
        return notes
    merged: list[DetectedNote] = []
    for note in notes:
        if merged:
            prev = merged[-1]
            gap = note.start - prev.end
            same_pitch = _semitone_distance(note.midi_note, prev.midi_note) <= tolerance
            if same_pitch and 0.0 <= gap <= max_gap:
                n = merged.pop()
                frames = n.frame_count + note.frame_count
                avg_conf = (n.confidence * n.frame_count + note.confidence * note.frame_count) / max(1, frames)
                merged.append(
                    DetectedNote(
                        frequency=(n.frequency + note.frequency) / 2.0,
                        midi_note=(n.midi_note + note.midi_note) / 2.0,
                        start=n.start,
                        end=note.end,
                        duration=note.end - n.start,
                        confidence=avg_conf,
                        f0_min=min(n.f0_min, note.f0_min),
                        f0_max=max(n.f0_max, note.f0_max),
                        frame_count=frames,
                    )
                )
                continue
        merged.append(note)
    return merged


class NoteSegmenter:
    """Segments pitch frames into notes using configurable thresholds."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def segment(self, frames: list[PitchFrame]) -> list[DetectedNote]:
        notes = self._segment_raw(frames)
        notes = self._filter(notes)
        notes = _merge_adjacent(notes, self.config.pitch_tolerance_semitones, max_gap=0.05)
        notes.sort(key=lambda n: n.start)
        return notes

    def _voiced_freqs(self, frames: list[PitchFrame]) -> list[float]:
        freqs: list[float] = []
        for frame in frames:
            if frame.voiced and frame.frequency is not None and frame.frequency > 0:
                freqs.append(round(float(frame.frequency), 4))
            else:
                freqs.append(0.0)
        if freqs:
            freqs = _median_smooth(freqs, self.config.smoothing_window)
        return freqs

    def _segment_raw(self, frames: list[PitchFrame]) -> list[DetectedNote]:
        conf_threshold = self.config.note_confidence_threshold
        freqs = self._voiced_freqs(frames)

        runs: list[list[int]] = []
        current: list[int] = []
        for i, frame in enumerate(frames):
            voiced = (
                frame.voiced
                and frame.frequency is not None
                and frame.frequency > 0
                and frame.confidence >= conf_threshold
            )
            if voiced:
                current.append(i)
            elif current:
                runs.append(current)
                current = []
        if current:
            runs.append(current)

        notes: list[DetectedNote] = []
        for run in runs:
            notes.extend(self._split_run(frames, freqs, run))
        return notes

    def _split_run(self, frames: list[PitchFrame], freqs: list[float], run: list[int]) -> list[DetectedNote]:
        tolerance = self.config.pitch_tolerance_semitones
        onset = self.config.onset_threshold_frames
        notes: list[DetectedNote] = []
        seg_start = run[0]
        pending = 0
        idx = seg_start + 1
        while idx <= run[-1]:
            cur = freqs[idx]
            ref_band = freqs[seg_start : idx + 1]
            ref_midi = _freq_to_midi(np.median([f for f in ref_band if f > 0])) if any(f > 0 for f in ref_band) else None
            cur_midi = _freq_to_midi(cur) if cur and cur > 0 else None
            if ref_midi is None or cur_midi is None:
                pending = 0
                idx += 1
                continue
            drift = _semitone_distance(cur_midi, ref_midi)
            if drift > tolerance:
                pending += 1
                if pending >= onset:
                    self._emit(notes, frames, freqs, seg_start, idx - onset + 1)
                    seg_start = idx - onset + 1
                    pending = 0
            else:
                pending = 0
            idx += 1
        if seg_start <= run[-1]:
            self._emit(notes, frames, freqs, seg_start, run[-1])
        return notes

    def _emit(self, notes: list[DetectedNote], frames: list[PitchFrame], freqs: list[float], a: int, b: int) -> None:
        band = [f for f in freqs[a : b + 1] if f > 0]
        if not band:
            return
        f_med = float(np.median(band))
        confs = [frames[i].confidence for i in range(a, b + 1) if frames[i].voiced]
        conf = float(np.mean(confs)) if confs else 0.0
        start = frames[a].time
        frame_slot = frames[1].time - frames[0].time if len(frames) > 1 else 0.02
        end = frames[b].time + frame_slot
        midi = _freq_to_midi(f_med)
        notes.append(
            DetectedNote(
                frequency=f_med,
                midi_note=midi,
                start=round(float(start), 6),
                end=round(float(end), 6),
                duration=round(float(end - start), 6),
                confidence=round(conf, 6),
                f0_min=float(min(band)),
                f0_max=float(max(band)),
                frame_count=b - a + 1,
            )
        )

    def _filter(self, notes: list[DetectedNote]) -> list[DetectedNote]:
        min_dur = self.config.min_note_duration
        min_conf = self.config.note_confidence_threshold
        keep = [n for n in notes if n.duration >= min_dur and n.confidence >= min_conf]
        return [n for n in keep if 0.0 <= n.midi_note <= 127.0]


# ---------------------------------------------------------------------------
# Helpers (local copies of freq↔MIDI to avoid circular imports with swara.py)
# ---------------------------------------------------------------------------

A4_FREQ = 440.0
A4_MIDI = 69


def _freq_to_midi(freq: float) -> float:
    import math
    if freq <= 0:
        raise ValueError("frequency must be > 0")
    return A4_MIDI + 12.0 * math.log2(freq / A4_FREQ)

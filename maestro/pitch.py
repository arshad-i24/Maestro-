"""Pitch detection and note segmentation.

Pitch detection: frame-level fundamental frequency estimation using
pYIN (default), STFT (fallback), or combined.

Note segmentation: converts continuous pitch frames into discrete musical
notes while filtering vibrato artifacts and merging adjacent same-pitch notes.
"""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
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
# Pitch Frame Processing (octave correction, vibrato stabilization)
# ---------------------------------------------------------------------------


@dataclass
class PitchDiagnostics:
    """Diagnostics from pitch frame processing."""
    total_frames: int = 0
    voiced_frames: int = 0
    unvoiced_frames: int = 0
    octave_corrections: int = 0
    freq_range_hz: tuple[float, float] = (0.0, 0.0)
    midi_range: tuple[float, float] = (0.0, 0.0)
    confidence_mean: float = 0.0
    confidence_min: float = 0.0
    confidence_max: float = 0.0


class PitchFrameProcessor:
    """Process raw pitch frames to correct octave errors and stabilize vibrato.

    This runs after pitch detection and before note segmentation.
    """

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        # Octave correction settings
        self.octave_threshold_semitones = 10.0  # Jump size to trigger octave check
        self.octave_correction_window = 5  # Frames to look around for context
        self.min_confidence_for_correction = 0.2  # Don't correct high-confidence frames
# Vibrato stabilization
        self.center_smoothing_window = 11  # Frames for center pitch tracking (must be odd, ~250ms)
        # Configurable via AppConfig
        self.octave_threshold_semitones = getattr(config, 'octave_correction_threshold', 10.0)
        self.octave_correction_window = getattr(config, 'octave_correction_window', 5)
        self.center_smoothing_window = getattr(config, 'center_smoothing_window', 11)
        self.min_confidence_for_correction = getattr(config, 'octave_min_confidence', 0.2)
        # Voicing threshold for stabilized frames
        self.stabilized_voice_threshold = getattr(config, 'stabilized_voice_threshold', 0.15)

    def process(self, frames: list[PitchFrame]) -> tuple[list[PitchFrame], PitchDiagnostics]:
        """Process pitch frames: correct octaves, stabilize vibrato.

        Returns:
            (processed_frames, diagnostics)
        """
        if not frames:
            return frames, PitchDiagnostics()

        # Step 1: Extract MIDI values for analysis
        midi_values = np.array([
            f.midi_note if f.voiced and f.midi_note is not None else np.nan
            for f in frames
        ])
        confidences = np.array([f.confidence for f in frames])
        voiced_flags = np.array([f.voiced for f in frames])

        # Step 2: Octave error correction
        corrected_midi = self._correct_octave_errors(midi_values, confidences, voiced_flags)

        # Step 3: Vibrato stabilization - track center frequency
        stabilized_midi = self._stabilize_vibrato(corrected_midi, confidences, voiced_flags)

        # Step 4: Re-evaluate voicing based on stabilized pitch continuity
        # If stabilized pitch forms a smooth track, mark as voiced even if raw confidence is low
        revoiced = self._reevaluate_voicing(stabilized_midi, confidences, voiced_flags)

        # Step 5: Boost confidence for corrected frames
        boosted_conf = self._boost_confidence(
            midi_values, corrected_midi, stabilized_midi, confidences, revoiced
        )

        # Step 6: Build corrected frames
        processed_frames = []
        octave_corrections = 0
        for i, frame in enumerate(frames):
            new_midi = stabilized_midi[i]
            new_conf = boosted_conf[i]
            new_voiced = revoiced[i]
            if not new_voiced or np.isnan(new_midi):
                new_frame = PitchFrame(
                    time=frame.time,
                    frequency=None,
                    voiced=False,
                    confidence=0.0,
                    midi_note=None,
                )
            else:
                new_freq = _midi_to_freq(new_midi)
                # Count octave corrections
                if frame.midi_note is not None and not np.isnan(frame.midi_note):
                    if abs(new_midi - frame.midi_note) > self.octave_threshold_semitones * 0.5:
                        octave_corrections += 1
                new_frame = PitchFrame(
                    time=frame.time,
                    frequency=new_freq,
                    voiced=new_voiced,
                    confidence=new_conf,
                    midi_note=new_midi,
                )
            processed_frames.append(new_frame)

        # Diagnostics
        voiced_midi = stabilized_midi[revoiced]
        voiced_conf = boosted_conf[revoiced]
        diag = PitchDiagnostics(
            total_frames=len(frames),
            voiced_frames=int(np.sum(revoiced)),
            unvoiced_frames=int(np.sum(~revoiced)),
            octave_corrections=octave_corrections,
            freq_range_hz=(
                float(_midi_to_freq(np.nanmin(voiced_midi))) if len(voiced_midi) > 0 else 0.0,
                float(_midi_to_freq(np.nanmax(voiced_midi))) if len(voiced_midi) > 0 else 0.0,
            ),
            midi_range=(
                float(np.nanmin(voiced_midi)) if len(voiced_midi) > 0 else 0.0,
                float(np.nanmax(voiced_midi)) if len(voiced_midi) > 0 else 0.0,
            ),
            confidence_mean=float(np.mean(voiced_conf)) if len(voiced_conf) > 0 else 0.0,
            confidence_min=float(np.min(voiced_conf)) if len(voiced_conf) > 0 else 0.0,
            confidence_max=float(np.max(voiced_conf)) if len(voiced_conf) > 0 else 0.0,
        )

        return processed_frames, diag

    def _correct_octave_errors(
        self,
        midi: np.ndarray,
        conf: np.ndarray,
        voiced: np.ndarray
    ) -> np.ndarray:
        """Correct brief octave jumps (~12 semitones) that are likely errors.

        Strategy:
        - Find frames where pitch jumps ~12 semitones from neighbors
        - Check if jump is brief (surrounded by stable pitch)
        - Check if confidence is low during jump (octave errors often have low confidence)
        - Only correct if contextual evidence strongly supports error
        """
        corrected = midi.copy()
        n = len(midi)

        for i in range(1, n - 1):
            if not voiced[i] or np.isnan(midi[i]):
                continue

            # Check jump from previous voiced frame
            prev_idx = i - 1
            while prev_idx >= 0 and (not voiced[prev_idx] or np.isnan(midi[prev_idx])):
                prev_idx -= 1
            if prev_idx < 0:
                continue

            # Check jump to next voiced frame
            next_idx = i + 1
            while next_idx < n and (not voiced[next_idx] or np.isnan(midi[next_idx])):
                next_idx += 1
            if next_idx >= n:
                continue

            jump_prev = abs(midi[i] - midi[prev_idx])
            jump_next = abs(midi[next_idx] - midi[i])

            # Check if this frame is an octave outlier
            is_octave_jump = (
                jump_prev > self.octave_threshold_semitones and
                jump_next > self.octave_threshold_semitones and
                abs(jump_prev - jump_next) < 2.0  # Jumps are similar (up then down or vice versa)
            )

            if is_octave_jump:
                # Check if neighbors agree on a stable pitch
                neighbor_midi = [midi[prev_idx], midi[next_idx]]
                neighbor_conf = [conf[prev_idx], conf[next_idx]]
                neighbors_agree = (
                    abs(neighbor_midi[0] - neighbor_midi[1]) <= 1.0 and
                    all(c > 0.3 for c in neighbor_conf)
                )
                
                # Correct if:
                # 1. Confidence is low (likely error), OR
                # 2. Neighbors strongly agree (contextual evidence)
                should_correct = (
                    conf[i] < self.min_confidence_for_correction or
                    (neighbors_agree and conf[i] < 0.6)
                )
                
                if should_correct:
                    corrected[i] = np.median(neighbor_midi)
                    logger.debug(
                        f"Octave correction at frame {i}: "
                        f"{midi[i]:.1f} -> {corrected[i]:.1f} MIDI "
                        f"(conf={conf[i]:.2f}, neighbors={neighbor_midi}, neighbors_agree={neighbors_agree})"
                    )

        return corrected

    def _stabilize_vibrato(
        self,
        midi: np.ndarray,
        conf: np.ndarray,
        voiced: np.ndarray
    ) -> np.ndarray:
        """Stabilize vibrato by tracking center frequency with longer smoothing.

        Uses a longer median filter to track the center pitch of vibrato,
        while preserving genuine pitch transitions.
        """
        n = len(midi)
        stabilized = np.full(n, np.nan)

        # Use longer median window for center frequency tracking
        half_window = self.center_smoothing_window // 2

        for i in range(n):
            if not voiced[i] or np.isnan(midi[i]):
                continue

            lo = max(0, i - half_window)
            hi = min(n, i + half_window + 1)
            window_midi = midi[lo:hi]
            window_voiced = voiced[lo:hi]
            window_conf = conf[lo:hi]

            # Only use voiced frames with reasonable confidence
            valid_mask = window_voiced & ~np.isnan(window_midi) & (window_conf > 0.1)
            valid_midi = window_midi[valid_mask]

            if len(valid_midi) >= 5:
                stabilized[i] = float(np.median(valid_midi))
            elif len(valid_midi) >= 2:
                stabilized[i] = float(np.median(valid_midi))
            else:
                stabilized[i] = midi[i]

        # Correct brief octave jumps in the stabilized track
        # (stabilized track may still have occasional outliers)
        stabilized = self._correct_stabilized_outliers(stabilized, voiced, conf)

        return stabilized

    def _correct_stabilized_outliers(
        self,
        stabilized: np.ndarray,
        voiced: np.ndarray,
        conf: np.ndarray
    ) -> np.ndarray:
        """Correct brief outliers in the stabilized pitch track."""
        corrected = stabilized.copy()
        n = len(stabilized)
        
        for i in range(2, n - 2):
            if not voiced[i] or np.isnan(stabilized[i]):
                continue
            
            # Check if this frame is an outlier relative to neighbors
            # in the STABILIZED track
            neighbors = []
            for di in [-2, -1, 1, 2]:
                ni = i + di
                if 0 <= ni < n and voiced[ni] and not np.isnan(stabilized[ni]):
                    neighbors.append(stabilized[ni])
            
            if len(neighbors) >= 3:
                neighbor_median = float(np.median(neighbors))
                deviation = abs(stabilized[i] - neighbor_median)
                
                # If deviation is large (> 3 semitones) and confidence is low
                if deviation > 3.0 and conf[i] < 0.3:
                    corrected[i] = neighbor_median
        
        return corrected

    def _reevaluate_voicing(
        self,
        stabilized_midi: np.ndarray,
        conf: np.ndarray,
        voiced: np.ndarray
    ) -> np.ndarray:
        """Re-evaluate voicing based on stabilized pitch continuity.

        If stabilized pitch forms a smooth track, keep frames voiced even if
        raw confidence was low. This helps with vibrato where pYIN confidence
        drops but pitch is actually continuous.

        Only re-voice originally voiced frames. Don't create new voiced frames
        from silence (previously unvoiced frames).
        """
        revoiced = voiced.copy()
        n = len(stabilized_midi)

        for i in range(1, n - 1):
            # Only consider frames that were originally voiced
            if not voiced[i] or np.isnan(stabilized_midi[i]):
                continue
            
            # Find nearest originally-voiced neighbors in stabilized pitch
            prev_idx = i - 1
            while prev_idx >= 0 and (not voiced[prev_idx] or np.isnan(stabilized_midi[prev_idx])):
                prev_idx -= 1
            next_idx = i + 1
            while next_idx < n and (not voiced[next_idx] or np.isnan(stabilized_midi[next_idx])):
                next_idx += 1
            
            if prev_idx >= 0 and next_idx < n:
                jump_prev = abs(stabilized_midi[i] - stabilized_midi[prev_idx])
                jump_next = abs(stabilized_midi[next_idx] - stabilized_midi[i])
                
                # If both jumps are small (< 2 semitones), this frame is part of a continuous track
                if jump_prev < 2.0 and jump_next < 2.0:
                    revoiced[i] = True
                # If this frame was marked unvoiced by confidence threshold but pitch is continuous
                elif not revoiced[i] and jump_prev < 2.0 and jump_next < 2.0:
                    revoiced[i] = True

        return revoiced

    def _boost_confidence(
        self,
        original_midi: np.ndarray,
        corrected_midi: np.ndarray,
        stabilized_midi: np.ndarray,
        conf: np.ndarray,
        voiced: np.ndarray
    ) -> np.ndarray:
        """Boost confidence for frames that were corrected/stabilized.

        When pitch is corrected based on strong contextual evidence,
        the confidence should reflect the corrected value's reliability.
        """
        boosted = conf.copy()
        n = len(conf)

        for i in range(n):
            if not voiced[i] or np.isnan(original_midi[i]):
                continue

            # If frame was corrected (octave or stabilization), boost confidence
            # based on neighbor confidence
            if abs(corrected_midi[i] - original_midi[i]) > 1.0:
                # Significant correction - check neighbors
                lo = max(0, i - 2)
                hi = min(n, i + 3)
                neighbor_conf = conf[lo:hi]
                neighbor_voiced = voiced[lo:hi]
                valid_conf = neighbor_conf[neighbor_voiced & (neighbor_conf > 0.01)]
                if len(valid_conf) >= 2:
                    boosted[i] = min(0.8, float(np.mean(valid_conf)))

            # If stabilization changed the pitch significantly, also boost
            elif abs(stabilized_midi[i] - corrected_midi[i]) > 0.5:
                lo = max(0, i - 2)
                hi = min(n, i + 3)
                neighbor_conf = conf[lo:hi]
                neighbor_voiced = voiced[lo:hi]
                valid_conf = neighbor_conf[neighbor_voiced & (neighbor_conf > 0.01)]
                if len(valid_conf) >= 2:
                    boosted[i] = min(0.7, float(np.mean(valid_conf)))
                else:
                    # No confident neighbors, but stabilized pitch is continuous
                    # Check if stabilized pitch matches surrounding stabilized pitch
                    lo2 = max(0, i - 3)
                    hi2 = min(n, i + 4)
                    window_midi = stabilized_midi[lo2:hi2]
                    window_voiced = voiced[lo2:hi2]
                    valid_midi = window_midi[window_voiced & ~np.isnan(window_midi)]
                    if len(valid_midi) >= 4:
                        if abs(stabilized_midi[i] - np.median(valid_midi)) < 1.0:
                            boosted[i] = max(boosted[i], 0.4)

            # For frames that are part of a stable region but had low raw confidence
            elif conf[i] < 0.3:
                lo = max(0, i - 3)
                hi = min(n, i + 4)
                window_midi = stabilized_midi[lo:hi]
                window_voiced = voiced[lo:hi]
                valid_midi = window_midi[window_voiced & ~np.isnan(window_midi)]
                if len(valid_midi) >= 4:
                    if abs(stabilized_midi[i] - np.median(valid_midi)) < 1.0:
                        boosted[i] = max(boosted[i], 0.3)

        return boosted


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


# ---------------------------------------------------------------------------
# Note Segmentation
# ---------------------------------------------------------------------------


class NoteSegmenter:
    """Segments pitch frames into notes using configurable thresholds."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.pitch_processor = PitchFrameProcessor(config)

    def segment(self, frames: list[PitchFrame]) -> list[DetectedNote]:
        # Process pitch frames (octave correction, vibrato stabilization)
        processed_frames, self._diagnostics = self.pitch_processor.process(frames)
        
        # Use RAW frames for boundary detection (sharp transitions)
        # Use PROCESSED frames for frequency estimation within notes
        notes = self._segment_raw(frames, processed_frames)
        notes = self._filter(notes)
        notes = _merge_adjacent(notes, self.config.pitch_tolerance_semitones, max_gap=0.05)
        notes.sort(key=lambda n: n.start)
        return notes

    def get_diagnostics(self) -> Optional['PitchDiagnostics']:
        """Return diagnostics from last processing."""
        return getattr(self, '_diagnostics', None)

    def _get_raw_voiced_freqs(self, frames: list[PitchFrame]) -> list[float]:
        """Get frequencies from raw frames for boundary detection."""
        freqs: list[float] = []
        for frame in frames:
            if frame.voiced and frame.frequency is not None and frame.frequency > 0:
                freqs.append(round(float(frame.frequency), 4))
            else:
                freqs.append(0.0)
        if freqs:
            freqs = _median_smooth(freqs, self.config.smoothing_window)
        return freqs

    def _get_processed_voiced_freqs(self, frames: list[PitchFrame]) -> list[float]:
        """Get frequencies from processed frames for note frequency estimation."""
        freqs: list[float] = []
        for frame in frames:
            if frame.voiced and frame.frequency is not None and frame.frequency > 0:
                freqs.append(round(float(frame.frequency), 4))
            else:
                freqs.append(0.0)
        return freqs  # No additional smoothing - already stabilized

    def _segment_raw(self, raw_frames: list[PitchFrame], processed_frames: list[PitchFrame]) -> list[DetectedNote]:
        conf_threshold = self.config.note_confidence_threshold
        # Use raw frames for boundary detection (voicing runs)
        raw_freqs = self._get_raw_voiced_freqs(raw_frames)
        # Use processed frames for frequency estimation
        proc_freqs = self._get_processed_voiced_freqs(processed_frames)

        runs: list[list[int]] = []
        current: list[int] = []
        for i, frame in enumerate(raw_frames):
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
            notes.extend(self._split_run(raw_frames, processed_frames, raw_freqs, proc_freqs, run))
        return notes

    def _split_run(self, raw_frames: list[PitchFrame], processed_frames: list[PitchFrame],
                   raw_freqs: list[float], proc_freqs: list[float], run: list[int]) -> list[DetectedNote]:
        tolerance = self.config.pitch_tolerance_semitones
        onset = self.config.onset_threshold_frames
        notes: list[DetectedNote] = []
        seg_start = run[0]
        pending = 0
        idx = seg_start + 1
        while idx <= run[-1]:
            # Use RAW frequencies for drift detection (sharp boundaries)
            cur = raw_freqs[idx]
            ref_band = raw_freqs[seg_start : idx + 1]
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
                    self._emit(notes, raw_frames, processed_frames, proc_freqs, seg_start, idx - onset + 1)
                    seg_start = idx - onset + 1
                    pending = 0
            else:
                pending = 0
            idx += 1
        if seg_start <= run[-1]:
            self._emit(notes, raw_frames, processed_frames, proc_freqs, seg_start, run[-1])
        return notes

    def _emit(self, notes: list[DetectedNote], raw_frames: list[PitchFrame], 
              processed_frames: list[PitchFrame], proc_freqs: list[float], a: int, b: int) -> None:
        # Use PROCESSED frequencies for note frequency estimation
        band = [f for f in proc_freqs[a : b + 1] if f > 0]
        if not band:
            return
        f_med = float(np.median(band))
        confs = [processed_frames[i].confidence for i in range(a, b + 1) if processed_frames[i].voiced]
        conf = float(np.mean(confs)) if confs else 0.0
        start = raw_frames[a].time
        frame_slot = raw_frames[1].time - raw_frames[0].time if len(raw_frames) > 1 else 0.02
        end = raw_frames[b].time + frame_slot
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
# Helpers
# ---------------------------------------------------------------------------

A4_FREQ = 440.0
A4_MIDI = 69


def _freq_to_midi(freq: float) -> float:
    if freq <= 0:
        raise ValueError("frequency must be > 0")
    return A4_MIDI + 12.0 * math.log2(freq / A4_FREQ)


def _midi_to_freq(midi: float) -> float:
    return A4_FREQ * (2.0 ** ((midi - A4_MIDI) / 12.0))
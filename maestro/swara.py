"""Hindustani swara conversion and pure music-theory helpers.

SwaraConverter: maps MIDI pitch → Hindustani swara relative to a configurable tonic (Sa).
TonicDetector: automatically estimates tonic (Sa) from detected vocal notes.
music_utils: frequency↔MIDI conversion, note names, cents, NaN checks.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from .errors import ErrorCode, MaestroError


# ---------------------------------------------------------------------------
# Pure music-theory helpers (frequency <-> MIDI, names, intervals)
# ---------------------------------------------------------------------------

A4_FREQ = 440.0
A4_MIDI = 69

_NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_NOTE_NAMES_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def freq_to_midi(freq: float) -> float:
    """Convert a frequency (Hz) to a *fractional* MIDI value."""
    if freq <= 0:
        raise ValueError("frequency must be > 0")
    return A4_MIDI + 12.0 * math.log2(freq / A4_FREQ)


def midi_to_freq(midi: float) -> float:
    """Convert a (possibly fractional) MIDI value to frequency in Hz."""
    return A4_FREQ * (2.0 ** ((midi - A4_MIDI) / 12.0))


def round_midi(midi: float) -> int:
    return int(round(midi))


def is_valid_midi(midi: float) -> bool:
    return 0.0 <= midi <= 127.0


def cents_between(freq_a: float, freq_b: float) -> float:
    if freq_a <= 0 or freq_b <= 0:
        return 0.0
    return 1200.0 * math.log2(freq_b / freq_a)


def midi_to_note_name(midi: float, prefer_flat: bool = False) -> str:
    pc = round_midi(midi) % 12
    octave = round_midi(midi) // 12 - 1
    table = _NOTE_NAMES_FLAT if prefer_flat else _NOTE_NAMES_SHARP
    return f"{table[pc]}{octave}"


def note_name_to_midi(name: str) -> Optional[int]:
    """Parse ``C4`` / ``C#4`` / ``Db3`` into a MIDI number, or None."""
    name = name.strip()
    if not name:
        return None
    letter = name[0].upper()
    if letter not in "ABCDEFG":
        return None
    pc = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[letter]
    idx = 1
    acc = 0
    while idx < len(name) and name[idx] in "#b♯♭":
        if name[idx] in "#♯":
            acc += 1
        else:
            acc -= 1
        idx += 1
    pc = (pc + acc) % 12
    try:
        octave = int(name[idx:])
    except (IndexError, ValueError):
        return None
    return (octave + 1) * 12 + pc


def is_finite_number(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def ensure_no_nan(container, path: str = "") -> None:
    """Recursively raise ValueError if a container holds NaN/Inf."""
    if isinstance(container, dict):
        for k, v in container.items():
            ensure_no_nan(v, f"{path}.{k}")
    elif isinstance(container, (list, tuple)):
        for i, v in enumerate(container):
            ensure_no_nan(v, f"{path}[{i}]")
    elif isinstance(container, (int, float)):
        if not math.isfinite(float(container)):
            raise ValueError(f"Non-finite value at {path or 'root'}: {container!r}")


# ---------------------------------------------------------------------------
# Hindustani Swara Conversion
# ---------------------------------------------------------------------------

_SWARA_TABLE = [
    ("Sa", "shuddha"),
    ("Re", "komal"),
    ("Re", "shuddha"),
    ("Ga", "komal"),
    ("Ga", "shuddha"),
    ("Ma", "shuddha"),
    ("Ma", "tivra"),
    ("Pa", "shuddha"),
    ("Dha", "komal"),
    ("Dha", "shuddha"),
    ("Ni", "komal"),
    ("Ni", "shuddha"),
]

VALID_SWARAS = {name for name, _ in _SWARA_TABLE}
OCTAVE_NAMES = {-1: "mandra", 0: "madhya", 1: "taar"}


@dataclass
class SwaraPitch:
    """A pitch expressed in Hindustani terms."""

    swara: str
    swara_type: str
    octave: str
    octave_index: int
    semitone_offset: int
    octave_shift: int
    cents_from_tonic: float
    midi_note: float
    frequency: float


class SwaraConverter:
    """Tonic-aware MIDI → swara converter."""

    def __init__(self, tonic_midi: Optional[int] = None) -> None:
        if tonic_midi is None:
            tonic_midi = 60
        self.tonic_midi = int(tonic_midi)
        if not 0 <= self.tonic_midi <= 127:
            raise MaestroError(ErrorCode.INVALID_TONIC, "tonic must be a MIDI note in 0..127")

    def tonic_frequency(self) -> float:
        return midi_to_freq(self.tonic_midi)

    def convert(self, midi_note: float, frequency: Optional[float] = None) -> SwaraPitch:
        if frequency is None:
            frequency = midi_to_freq(midi_note)
        cents = 1200.0 * (midi_note - self.tonic_midi)
        rounded_semis = int(round(midi_note - self.tonic_midi))
        octave_shift = rounded_semis // 12
        semitone_offset = rounded_semis % 12
        if octave_shift >= 2 or octave_shift <= -2:
            sign = "+" if octave_shift > 0 else "-"
            octave_name = f"extended{sign}"
        else:
            octave_name = OCTAVE_NAMES[octave_shift]
        swara, swara_type = _SWARA_TABLE[semitone_offset]
        return SwaraPitch(
            swara=swara,
            swara_type=swara_type,
            octave=octave_name,
            octave_index=octave_shift,
            semitone_offset=semitone_offset,
            octave_shift=octave_shift,
            cents_from_tonic=cents,
            midi_note=float(midi_note),
            frequency=float(frequency),
        )


def swara_for_midi(midi_note: float, tonic_midi: Optional[int] = None) -> SwaraPitch:
    return SwaraConverter(tonic_midi).convert(midi_note)


# ---------------------------------------------------------------------------
# Automatic Tonic (Sa) Detection
# ---------------------------------------------------------------------------

# Consonant intervals from tonic (in semitones) that are musically significant
# in Hindustani music. Weight by musical importance.
_CONSONANT_INTERVALS = {
    0: 1.0,    # Sa (unison)
    7: 0.9,    # Pa (perfect fifth)
    5: 0.8,    # Ma (perfect fourth)
    4: 0.7,    # Ga (major third)
    9: 0.6,    # Dha (major sixth)
    2: 0.5,    # Re (major second)
    11: 0.4,   # Ni (major seventh)
    3: 0.3,    # komal Ga (minor third)
    8: 0.3,    # komal Dha (minor sixth)
    1: 0.2,    # komal Re (minor second)
    10: 0.2,   # komal Ni (minor seventh)
    6: 0.1,    # tivra Ma (augmented fourth / diminished fifth)
}


@dataclass
class TonicCandidate:
    """A candidate tonic with its score and supporting evidence."""
    midi: int
    score: float
    supporting_notes: int
    total_duration: float
    avg_confidence: float
    # Per-interval note counts for debugging
    interval_evidence: dict[int, float]


class TonicDetector:
    """Detects tonic (Sa) from a sequence of vocal notes.

    The tonic is estimated by finding the pitch class that best explains
    the observed note distribution as consonant intervals.
    """

    def __init__(
        self,
        min_confidence: float = 0.3,
        min_duration: float = 0.05,
        min_supporting_notes: int = 3,
        score_threshold: float = 1.0,
        ambiguity_ratio: float = 1.1,
    ) -> None:
        self.min_confidence = min_confidence
        self.min_duration = min_duration
        self.min_supporting_notes = min_supporting_notes
        self.score_threshold = score_threshold
        self.ambiguity_ratio = ambiguity_ratio

    def detect(self, notes: list) -> Optional[int]:
        """Detect tonic from detected notes.

        Args:
            notes: List of DetectedNote objects with midi_note, frequency, duration, confidence

        Returns:
            MIDI note number of detected tonic, or None if detection is unreliable
        """
        if not notes:
            return None

        # Filter valid notes
        valid_notes = [
            n for n in notes
            if n.confidence >= self.min_confidence
            and n.duration >= self.min_duration
            and 0 <= n.midi_note <= 127
        ]

        if len(valid_notes) < self.min_supporting_notes:
            return None

        # For each unique pitch class (0-11), evaluate as tonic candidate
        candidates = self._evaluate_candidates(valid_notes)

        if not candidates:
            return None

        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)

        # Post-process: resolve fifth-above ambiguities
        # If a candidate is a perfect fifth (7 semitones) above another strong candidate,
        # the lower one is more likely the tonic
        candidates = self._resolve_fifth_ambiguity(candidates)

        # Re-sort after resolution
        candidates.sort(key=lambda c: c.score, reverse=True)

        best = candidates[0]

        # Check if best candidate meets threshold
        if best.score < self.score_threshold:
            return None

        # Check for ambiguity
        if len(candidates) > 1:
            second = candidates[1]
            if best.score / max(second.score, 1e-6) < self.ambiguity_ratio:
                return None

        return best.midi

    def _resolve_fifth_ambiguity(self, candidates: list) -> list:
        """Resolve ambiguities where a candidate is a fifth above another.

        In Hindustani music, if both X and X+7 are strong candidates,
        X is more likely the tonic (Sa) and X+7 is Pa.
        """
        if len(candidates) < 2:
            return candidates

        # Create a set of candidate MIDI values for fast lookup
        candidate_map = {c.midi: c for c in candidates}

        # Check each candidate: if there's another candidate a fifth below it,
        # boost the lower one and/or penalize the upper one
        for c in candidates:
            fifth_below = c.midi - 7
            if fifth_below in candidate_map:
                lower = candidate_map[fifth_below]
                # If lower candidate is also strong, it's likely the tonic
                # Boost lower, penalize upper
                if lower.score > self.score_threshold:
                    # Transfer some score from upper to lower
                    transfer = min(c.score * 0.3, lower.score * 0.5)
                    lower.score += transfer
                    c.score -= transfer

        return candidates

    def _evaluate_candidates(self, notes: list) -> list[TonicCandidate]:
        """Evaluate all 12 pitch classes as tonic candidates.

        For each pitch class, evaluate multiple relevant octaves and pick the best.
        """
        # Normalize all notes to their pitch class (0-11) with octave info
        note_data = []
        for n in notes:
            pc = int(round(n.midi_note)) % 12
            octave = int(round(n.midi_note)) // 12
            note_data.append({
                'pc': pc,
                'octave': octave,
                'midi': int(round(n.midi_note)),
                'frequency': n.frequency,
                'duration': n.duration,
                'confidence': n.confidence,
            })

        candidates = []

        # Test each of the 12 pitch classes as potential tonic
        for tonic_pc in range(12):
            # Get all octaves where this pitch class appears in the melody
            tonic_octaves = [d['octave'] for d in note_data if d['pc'] == tonic_pc]
            
            if tonic_octaves:
                # Evaluate each octave where tonic appears
                for octave in set(tonic_octaves):
                    tonic_midi = tonic_pc + 12 * octave
                    candidate = self._score_candidate(tonic_midi, note_data, tonic_pc)
                    if candidate:
                        candidates.append(candidate)
            else:
                # No direct tonic notes - estimate octave from consonant intervals
                octaves = []
                for d in note_data:
                    interval = (d['pc'] - tonic_pc) % 12
                    if interval in _CONSONANT_INTERVALS and _CONSONANT_INTERVALS[interval] > 0.3:
                        octaves.append(d['octave'])
                if octaves:
                    # Use median octave
                    est_octave = int(round(sum(octaves) / len(octaves)))
                    tonic_midi = tonic_pc + 12 * est_octave
                    candidate = self._score_candidate(tonic_midi, note_data, tonic_pc)
                    if candidate:
                        candidates.append(candidate)
                else:
                    # Fallback: use overall median octave
                    all_octaves = [d['octave'] for d in note_data]
                    est_octave = int(round(sum(all_octaves) / len(all_octaves)))
                    tonic_midi = tonic_pc + 12 * est_octave
                    candidate = self._score_candidate(tonic_midi, note_data, tonic_pc)
                    if candidate:
                        candidates.append(candidate)

        return candidates

    def _estimate_tonic_midi(self, tonic_pc: int, note_data: list) -> int:
        """Estimate tonic MIDI when no direct Sa notes exist.

        Use the most common octave among consonant interval notes.
        """
        octaves = []
        for d in note_data:
            interval = (d['pc'] - tonic_pc) % 12
            if interval in _CONSONANT_INTERVALS and _CONSONANT_INTERVALS[interval] > 0.3:
                octaves.append(d['octave'])
        if octaves:
            return tonic_pc + 12 * int(round(sum(octaves) / len(octaves)))
        # Fallback: use overall median octave
        all_octaves = [d['octave'] for d in note_data]
        return tonic_pc + 12 * int(round(sum(all_octaves) / len(all_octaves)))

    def _score_candidate(self, tonic_midi: int, note_data: list, tonic_pc: int) -> Optional[TonicCandidate]:
        """Score a tonic candidate based on note evidence."""
        interval_evidence = {}
        total_weight = 0.0
        supporting_count = 0
        total_duration = 0.0
        confidence_sum = 0.0
        unison_count = 0
        unison_duration = 0.0

        for d in note_data:
            interval = (d['pc'] - tonic_pc) % 12
            weight = _CONSONANT_INTERVALS.get(interval, 0.0)

            if weight > 0:
                # Weight by interval importance, note duration, and confidence
                evidence_weight = weight * d['duration'] * d['confidence']
                total_weight += evidence_weight
                interval_evidence[interval] = interval_evidence.get(interval, 0.0) + evidence_weight
                supporting_count += 1
                total_duration += d['duration']
                confidence_sum += d['confidence']

                # Track unison (exact tonic) matches separately
                if interval == 0:
                    unison_count += 1
                    unison_duration += d['duration']

        if supporting_count < self.min_supporting_notes:
            return None

        avg_confidence = confidence_sum / supporting_count if supporting_count > 0 else 0.0

        # Add unison bonus: direct tonic matches are strong evidence
        if unison_count > 0:
            unison_bonus = unison_duration * 0.5  # Bonus proportional to tonic note duration
            total_weight += unison_bonus
            interval_evidence[0] = interval_evidence.get(0, 0.0) + unison_bonus

        # Framing bonus: if first or last note matches tonic pitch class, strong evidence
        if note_data:
            first_pc = note_data[0]['pc']
            last_pc = note_data[-1]['pc']
            if first_pc == tonic_pc:
                total_weight += note_data[0]['duration'] * note_data[0]['confidence'] * 0.8
                interval_evidence[0] = interval_evidence.get(0, 0.0) + note_data[0]['duration'] * note_data[0]['confidence'] * 0.8
            if last_pc == tonic_pc:
                total_weight += note_data[-1]['duration'] * note_data[-1]['confidence'] * 0.8
                interval_evidence[0] = interval_evidence.get(0, 0.0) + note_data[-1]['duration'] * note_data[-1]['confidence'] * 0.8

        # Frequency bonus: if a note appears most frequently (by duration) at this pitch class
        pc_durations = {}
        for d in note_data:
            pc_durations[d['pc']] = pc_durations.get(d['pc'], 0.0) + d['duration']
        if pc_durations:
            max_dur = max(pc_durations.values())
            if pc_durations.get(tonic_pc, 0) == max_dur and max_dur > 0:
                total_weight += max_dur * 0.3
                interval_evidence[0] = interval_evidence.get(0, 0.0) + max_dur * 0.3

        return TonicCandidate(
            midi=tonic_midi,
            score=total_weight,
            supporting_notes=supporting_count,
            total_duration=total_duration,
            avg_confidence=avg_confidence,
            interval_evidence=interval_evidence,
        )


def detect_tonic(notes: list, **kwargs) -> Optional[int]:
    """Convenience function for tonic detection."""
    detector = TonicDetector(**kwargs)
    return detector.detect(notes)

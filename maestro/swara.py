"""Hindustani swara conversion and pure music-theory helpers.

SwaraConverter: maps MIDI pitch → Hindustani swara relative to a configurable tonic (Sa).
music_utils: frequency↔MIDI conversion, note names, cents, NaN checks.
"""

from __future__ import annotations

import math
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

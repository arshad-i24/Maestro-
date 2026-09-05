"""Musical notation generator (Hindustani style).

Converts detected notes + swaras into readable structured notation entries.

Octave markers:
* ``.Sa`` = mandra (lower)
* ``Sa`` = madhya (middle)
* ``'Sa`` = taar (upper)

Accidentals: komal → lowercase (r g d n), tivra Ma → ``M#``.
"""

from __future__ import annotations

from typing import Optional

from .models import NotationEntryOut
from .swara import SwaraConverter, SwaraPitch

_SYMBOL = {
    ("Sa", "shuddha"): "S",
    ("Re", "komal"): "R(k)",
    ("Re", "shuddha"): "R",
    ("Ga", "komal"): "G(k)",
    ("Ga", "shuddha"): "G",
    ("Ma", "shuddha"): "m",
    ("Ma", "tivra"): "M",
    ("Pa", "shuddha"): "P",
    ("Dha", "komal"): "D(k)",
    ("Dha", "shuddha"): "D",
    ("Ni", "komal"): "N(k)",
    ("Ni", "shuddha"): "N",
}

_LOW_OCTAVE_LOWERCASE = {"Pa", "Dha", "Ni"}


def render_swara_symbol(swara: SwaraPitch) -> str:
    base = _SYMBOL.get((swara.swara, swara.swara_type), swara.swara)

    if swara.octave == "madhya":
        return base
    if swara.octave == "mandra":
        if swara.swara in _LOW_OCTAVE_LOWERCASE:
            return base.lower()
        return f".{base}"
    if swara.octave == "taar":
        return f"{base}'"
    if swara.octave.startswith("extended"):
        shift = swara.octave_index
        prefix = "." if shift < 0 else "'"
        return f"{prefix * abs(shift)}{base}"
    return base


class NotationGenerator:
    """Structured Hindustani notation from notes + optional lyric mapping."""

    def __init__(self, converter: SwaraConverter) -> None:
        self.converter = converter

    def generate(
        self,
        notes: list,
        lyric_map: Optional[dict[int, str]] = None,
    ) -> list[NotationEntryOut]:
        entries: list[NotationEntryOut] = []
        for idx, note in enumerate(notes):
            pitch = self.converter.convert(note.midi_note, note.frequency)
            lyric = lyric_map.get(idx) if lyric_map else None
            entries.append(
                NotationEntryOut(
                    swara=pitch.swara,
                    octave=pitch.octave,
                    start=round(float(note.start), 6),
                    end=round(float(note.end), 6),
                    duration=round(float(note.duration), 6),
                    lyric=lyric,
                    confidence=round(float(note.confidence), 6),
                    symbol=render_swara_symbol(pitch),
                )
            )
        return entries

    @staticmethod
    def render_sequence(entries: list[NotationEntryOut]) -> str:
        return " ".join(entry.symbol for entry in entries)

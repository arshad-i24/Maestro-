"""Musical notation generator (Hindustani style).

Converts detected notes + swaras into readable structured notation entries.

Octave markers:
* Lower octave (mandra): lowercase (s, r, g, m, p, d, n)
* Middle octave (madhya): uppercase (S, R, G, m, P, D, N)
* Higher octave (taar): uppercase + apostrophe (S', R', G', m', P', D', N')

Accidentals: komal uses (k) suffix, tivra Ma uses M.
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


def render_swara_symbol(swara: SwaraPitch) -> str:
    """Render a swara pitch as Hindustani notation symbol.

    Octave convention:
    - mandra (lower): lowercase (s, r, g, m, p, d, n, r(k), g(k), etc.)
    - madhya (middle): uppercase (S, R, G, m, P, D, N, R(k), G(k), etc.)
    - taar (higher): uppercase + apostrophe (S', R', G', m', P', D', N', etc.)
    - extended: multiple apostrophes or lowercase prefixes
    """
    base = _SYMBOL.get((swara.swara, swara.swara_type), swara.swara)

    if swara.octave == "madhya":
        return base
    if swara.octave == "mandra":
        # Lower octave: use lowercase for all notes
        return base.lower()
    if swara.octave == "taar":
        # Higher octave: add apostrophe
        return f"{base}'"
    if swara.octave.startswith("extended"):
        shift = swara.octave_index
        if shift < 0:
            # Multiple lower octaves: more lowercase (already lowercase, add more markers)
            return f"{'.' * abs(shift)}{base.lower()}"
        else:
            # Multiple higher octaves: more apostrophes
            apostrophe = "'"
            return f"{base}{apostrophe * shift}"
    return base


class NotationGenerator:
    """Structured Hindustani notation from notes + optional lyric mapping."""

    def __init__(self, converter: SwaraConverter) -> None:
        self.converter = converter

    def generate(
        self,
        notes: list,
        lyric_map: Optional[dict[int, list[str]]] = None,
    ) -> list[NotationEntryOut]:
        entries: list[NotationEntryOut] = []
        for idx, note in enumerate(notes):
            pitch = self.converter.convert(note.midi_note, note.frequency)
            lyrics_list = lyric_map.get(idx) if lyric_map else None
            # Join multiple lyrics with a separator for display
            lyric = ", ".join(lyrics_list) if lyrics_list else None
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

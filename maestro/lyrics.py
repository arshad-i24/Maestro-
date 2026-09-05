"""Lyric text processing and lyric-to-note alignment.

LyricProcessor: tokenizes text into words, splits syllables (vowel-group heuristic).
LyricAligner: time-proportional word placement over detected note span.
"""

from __future__ import annotations

import logging
import re

from .config import AppConfig
from .errors import ErrorCode, MaestroError
from .models import DetectedNote, LyricUnit

logger = logging.getLogger("maestro.lyrics")

_VOWEL = "aeiouyAEIOUY"


# ---------------------------------------------------------------------------
# Lyric Processing
# ---------------------------------------------------------------------------


def split_syllables(word: str) -> list[str]:
    """Split word into syllables with a consonant+vowel heuristic."""
    word = word.strip()
    if not word:
        return []
    if not any(c in _VOWEL for c in word):
        return [word]

    groups: list[str] = []
    cur = ""
    prev_is_vowel = False
    for ch in word:
        if not (ch.isalpha() or ch in "'-'"):
            continue
        is_vowel = ch in _VOWEL
        if is_vowel:
            cur += ch
        else:
            if cur and prev_is_vowel:
                groups.append(cur)
                cur = ""
            cur += ch
        prev_is_vowel = is_vowel
    if cur:
        groups.append(cur)
    return groups


class LyricProcessor:
    def process(self, text: str) -> list[LyricUnit]:
        text = (text or "").strip()
        if not text:
            raise MaestroError(ErrorCode.LYRICS_ALIGNMENT_FAILED, "lyrics text is empty")
        words = text.split()
        units: list[LyricUnit] = []
        for i, word in enumerate(words):
            cleaned = re.sub(r"[^\w'']", "", word.strip())
            if not cleaned:
                continue
            units.append(
                LyricUnit(
                    word=cleaned,
                    index=i,
                    syllables=split_syllables(cleaned),
                )
            )
        if not units:
            raise MaestroError(ErrorCode.LYRICS_ALIGNMENT_FAILED, "no usable lyric words found")
        return units


# ---------------------------------------------------------------------------
# Lyric-to-Note Alignment
# ---------------------------------------------------------------------------


class LyricAligner:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def align(self, units: list[LyricUnit], notes: list[DetectedNote]) -> list[LyricUnit]:
        if not notes:
            raise MaestroError(
                ErrorCode.LYRICS_ALIGNMENT_FAILED,
                "cannot align lyrics: no musical notes detected",
            )
        if not units:
            raise MaestroError(ErrorCode.LYRICS_ALIGNMENT_FAILED, "no lyric units to align")

        span_start = notes[0].start
        span_end = notes[-1].end
        span = max(1e-6, span_end - span_start)

        weights = [max(1, len(u.syllables)) for u in units]
        total = sum(weights)

        cursor = 0.0
        slots: list[tuple[float, float]] = []
        for w in weights:
            start = span_start + cursor * span / total
            cursor += w
            end = span_start + cursor * span / total
            slots.append((start, end))

        out: list[LyricUnit] = []
        for unit, (slot_start, slot_end) in zip(units, slots):
            attached = [
                (i, n) for i, n in enumerate(notes) if _overlaps(n, slot_start, slot_end)
            ]
            if not attached:
                idx = min(range(len(notes)), key=lambda i: _distance(notes[i], slot_start))
                attached = [(idx, notes[idx])]
            attached.sort(key=lambda it: it[1].start)
            note_idx = [i for i, _ in attached]
            first = attached[0][1]
            last = attached[-1][1]

            seg_start = first.start
            seg_end = last.end

            covered = sum(max(0.0, min(seg_end, n.end) - max(seg_start, n.start)) for _, n in attached)
            slot_len = max(1e-6, slot_end - slot_start)
            timing_conf = min(1.0, covered / slot_len)
            pitch_conf = float(min(max(n.confidence for _, n in attached), 1.0))
            confidence = round(0.6 * timing_conf + 0.4 * pitch_conf, 4)

            unit.start = round(seg_start, 6)
            unit.end = round(seg_end, 6)
            unit.notes = note_idx
            unit.confidence = confidence
            unit.alignment_method = "time-proportional"
            out.append(unit)

        return out


def _overlaps(note: DetectedNote, start: float, end: float) -> bool:
    return note.end > start and note.start < end


def _distance(note: DetectedNote, t: float) -> float:
    if note.start <= t <= note.end:
        return 0.0
    return min(abs(note.start - t), abs(note.end - t))

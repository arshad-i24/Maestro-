"""Output validation utilities.

Ensures every result the engine produces is well-formed before it is
returned: no NaN/Inf, ordered note times, positive durations, valid MIDI
pitches, valid swaras, and confidence bounded to [0, 1].
"""

from __future__ import annotations

import math
from typing import Any

from .models import (
    DetectedNote,
    MaestroResult,
    SwaraOut,
)
from .swara import VALID_SWARAS, ensure_no_nan

VALID_SWARA_TYPES = {"shuddha", "komal", "tivra"}
VALID_OCTAVES = {"mandra", "madhya", "taar"}


class OutputValidator:
    def validate_notes(self, notes: list[DetectedNote]) -> None:
        prev_end = 0.0
        for note in notes:
            if not (math.isfinite(note.start) and math.isfinite(note.end) and note.duration > 0):
                raise ValueError(f"note with invalid timing: {note!r}")
            if note.end < note.start or note.duration <= 0:
                raise ValueError(f"note violates ordering: {note!r}")
            if note.end < prev_end - 1e-6:
                raise ValueError(f"note times not sorted: {note!r}")
            prev_end = max(prev_end, note.end)
            if not (0.0 <= note.midi_note <= 127.0):
                raise ValueError(f"midi pitch out of range: {note.midi_note}")

    def validate_result(self, result: MaestroResult) -> None:
        ensure_no_nan(result.model_dump(mode="json"))

        for swara in result.swaras:
            if swara.swara not in VALID_SWARAS:
                raise ValueError(f"invalid swara: {swara.swara}")
            if swara.swara_type not in VALID_SWARA_TYPES:
                raise ValueError(f"invalid swara_type: {swara.swara_type}")
            if swara.octave not in VALID_OCTAVES and not swara.octave.startswith("extended"):
                raise ValueError(f"invalid octave: {swara.octave}")
            if not (0.0 <= swara.confidence <= 1.0):
                raise ValueError(f"swara confidence out of range: {swara.confidence}")

        if result.midi:
            prev = 0.0
            for note in result.midi.notes:
                if not (0 <= note.pitch <= 127):
                    raise ValueError(f"midi pitch out of range: {note.pitch}")
                if not (note.end >= note.start and note.duration > 0):
                    raise ValueError(f"midi note invalid: {note!r}")
                if note.start < prev - 1e-6:
                    raise ValueError(f"midi notes not ordered: {note!r}")
                prev = max(prev, note.start)

        for entry in result.notation:
            if not (math.isfinite(entry.duration) and entry.duration > 0):
                raise ValueError(f"notation entry invalid: {entry!r}")
            if not (0.0 <= entry.confidence <= 1.0):
                raise ValueError(f"notation confidence out of range: {entry.confidence}")

        if result.lyrics and result.lyrics.segments:
            for seg in result.lyrics.segments:
                if not (seg.end >= seg.start):
                    raise ValueError(f"lyric segment invalid timing: {seg!r}")
                if not (0.0 <= seg.confidence <= 1.0):
                    raise ValueError(f"lyric confidence out of range: {seg.confidence}")

    @staticmethod
    def validate_midi_file(path: str) -> None:
        """Re-open the MIDI file with mido and assert it parses with notes."""
        try:
            import mido
        except ImportError as exc:
            raise ValueError("mido not installed; cannot validate MIDI file") from exc
        mid = mido.MidiFile(path)
        notes_on = sum(1 for t in mid.tracks for m in t if m.type == "note_on")
        notes_off = sum(1 for t in mid.tracks for m in t if m.type == "note_off")
        if notes_on == 0 or notes_on != notes_off:
            raise ValueError(f"MIDI file has unbalanced/empty note events (on={notes_on}, off={notes_off})")


def validate_dict_sections(data: dict[str, Any]) -> None:
    """Lightweight sanity checks on the serialized top-level sections."""
    stats = data.get("statistics")
    if isinstance(stats, dict) and stats.get("total_seconds", 0) is not None:
        if stats["total_seconds"] < 0:
            raise ValueError("statistics.total_seconds must be >= 0")
    if isinstance(stats, dict) and sum(stats.get("stages", {}).values()) > 0:
        pass  # stage timings are informational only
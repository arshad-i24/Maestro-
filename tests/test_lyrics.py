import pytest

from maestro.errors import ErrorCode, MaestroError
from maestro.lyrics import LyricAligner, LyricProcessor, split_syllables
from maestro.models import DetectedNote


def _notes():
    return [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.10, end=0.42, duration=0.32, confidence=0.9),
        DetectedNote(frequency=329.63, midi_note=64.0, start=0.44, end=0.82, duration=0.38, confidence=0.85),
        DetectedNote(frequency=392.0, midi_note=67.0, start=0.84, end=1.30, duration=0.46, confidence=0.93),
        DetectedNote(frequency=261.63, midi_note=60.0, start=1.34, end=1.62, duration=0.28, confidence=0.8),
    ]


def test_processor_words_and_syllables():
    units = LyricProcessor().process("tu  maana  gaana hai")
    assert [u.word for u in units] == ["tu", "maana", "gaana", "hai"]
    assert units[1].syllables == ["maa", "na"]


def test_split_syllables_basic():
    assert split_syllables("tu") == ["tu"]
    assert split_syllables("sa") == ["sa"]
    assert split_syllables("abc") == ["a", "bc"]  # a is a vowel → splits
    assert split_syllables("mnm") == ["mnm"]  # no vowels → kept whole


def test_processor_empty_raises():
    with pytest.raises(MaestroError) as exc:
        LyricProcessor().process("   ")
    assert exc.value.code == ErrorCode.LYRICS_ALIGNMENT_FAILED


def test_alignment_basic(config):
    units = LyricProcessor().process("tu maana gaana")
    aligned = LyricAligner(config).align(units, _notes())
    assert len(aligned) == 3
    for u in aligned:
        assert u.start is not None and u.end is not None
        assert u.end >= u.start
        assert 0.0 <= u.confidence <= 1.0
        assert u.notes, "every word should attach at least one note"


def test_melisma_multiple_notes_per_word(config):
    """One word spanning two notes keeps BOTH notes (melisma)."""
    notes = _notes()
    units = LyricProcessor().process("tuuu")  # single long word
    aligned = LyricAligner(config).align(units, notes)
    assert len(aligned[0].notes) >= 2


def test_alignment_no_notes_raises(config):
    with pytest.raises(MaestroError) as exc:
        LyricAligner(config).align(LyricProcessor().process("tu"), [])
    assert exc.value.code == ErrorCode.LYRICS_ALIGNMENT_FAILED


def test_confidence_in_range(config):
    units = LyricProcessor().process("a  b  c")
    aligned = LyricAligner(config).align(units, _notes())
    assert all(0.0 <= u.confidence <= 1.0 for u in aligned)
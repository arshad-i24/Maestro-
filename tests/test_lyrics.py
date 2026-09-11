import pytest

from maestro.errors import ErrorCode, MaestroError
from maestro.lyrics import LyricAligner, LyricProcessor, split_syllables
from maestro.models import DetectedNote
from maestro.lyric_asr import WordTimestamp


def _notes():
    return [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.10, end=0.42, duration=0.32, confidence=0.9),
        DetectedNote(frequency=329.63, midi_note=64.0, start=0.44, end=0.82, duration=0.38, confidence=0.85),
        DetectedNote(frequency=392.0, midi_note=67.0, start=0.84, end=1.30, duration=0.46, confidence=0.93),
        DetectedNote(frequency=261.63, midi_note=60.0, start=1.34, end=1.62, duration=0.28, confidence=0.8),
    ]


def _whisper_words(words_timing: list[tuple[str, float, float]]) -> list[WordTimestamp]:
    """Helper to create Whisper word timestamps."""
    return [WordTimestamp(word=w, start=s, end=e, confidence=0.9) for w, s, e in words_timing]


def test_processor_words_and_syllables():
    units = LyricProcessor().process("tu  maana  gaana hai")
    assert [u.word for u in units] == ["tu", "maana", "gaana", "hai"]
    assert units[1].syllables == ["maa", "na"]


def test_split_syllables_basic():
    assert split_syllables("tu") == ["tu"]
    assert split_syllables("sa") == ["sa"]
    assert split_syllables("abc") == ["a", "bc"]  # a is a vowel -> splits
    assert split_syllables("mnm") == ["mnm"]  # no vowels -> kept whole


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


# ============================================================
# NEW TESTS: Primary ownership model, no over-attaching
# ============================================================

def test_whisper_one_word_one_note(config):
    """One word -> one note (exact match)."""
    notes = [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.10, end=0.35, duration=0.25, confidence=0.9),
        DetectedNote(frequency=329.63, midi_note=64.0, start=0.35, end=0.75, duration=0.40, confidence=0.85),
        DetectedNote(frequency=392.0, midi_note=67.0, start=0.75, end=1.15, duration=0.40, confidence=0.93),
        DetectedNote(frequency=261.63, midi_note=60.0, start=1.15, end=1.55, duration=0.40, confidence=0.8),
        DetectedNote(frequency=392.0, midi_note=67.0, start=1.55, end=1.95, duration=0.40, confidence=0.9),
    ]
    whisper_words = _whisper_words([
        ("tu", 0.10, 0.35),
        ("hi", 0.35, 0.75),
        ("mera", 0.75, 1.15),
        ("dil", 1.15, 1.55),
        ("hai", 1.55, 1.95),
    ])
    
    processor = LyricProcessor()
    units = processor.process_with_whisper_timestamps("tu hi mera dil hai", whisper_words)
    aligned = LyricAligner(config).align(units, notes)
    
    assert len(aligned) == 5
    # Each word should map to exactly one note
    assert aligned[0].notes == [0]  # tu -> N0
    assert aligned[1].notes == [1]  # hi -> N1
    assert aligned[2].notes == [2]  # mera -> N2
    assert aligned[3].notes == [3]  # dil -> N3
    assert aligned[4].notes == [4]  # hai -> N4
    
    # No note should have multiple primary lyrics
    note_to_words = {}
    for u in aligned:
        for n_idx in u.notes:
            if n_idx not in note_to_words:
                note_to_words[n_idx] = []
            note_to_words[n_idx].append(u.word)
    
    for n_idx, words in note_to_words.items():
        assert len(words) == 1, f"Note {n_idx} has multiple primary lyrics: {words}"


def test_whisper_melisma_one_word_multiple_notes(config):
    """One word spanning multiple notes (melisma)."""
    notes = [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.10, end=0.40, duration=0.30, confidence=0.9),
        DetectedNote(frequency=293.66, midi_note=62.0, start=0.40, end=0.70, duration=0.30, confidence=0.85),
        DetectedNote(frequency=329.63, midi_note=64.0, start=0.70, end=1.00, duration=0.30, confidence=0.93),
        DetectedNote(frequency=349.23, midi_note=65.0, start=1.00, end=1.30, duration=0.30, confidence=0.8),
    ]
    whisper_words = _whisper_words([
        ("dil", 0.10, 1.00),  # spans first 3 notes
        ("hai", 1.00, 1.30),
    ])
    
    processor = LyricProcessor()
    units = processor.process_with_whisper_timestamps("dil hai", whisper_words)
    aligned = LyricAligner(config).align(units, notes)
    
    assert len(aligned) == 2
    # "dil" should own notes 0, 1, 2 (melisma)
    assert 0 in aligned[0].notes
    assert 1 in aligned[0].notes
    assert 2 in aligned[0].notes
    # "hai" should own note 3
    assert aligned[1].notes == [3]


def test_whisper_multiple_words_same_note(config):
    """Two words within one long note - note has one primary owner, other word unmatched."""
    notes = [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.10, end=1.00, duration=0.90, confidence=0.9),
        DetectedNote(frequency=329.63, midi_note=64.0, start=1.00, end=1.50, duration=0.50, confidence=0.85),
    ]
    whisper_words = _whisper_words([
        ("tu", 0.10, 0.45),
        ("hi", 0.45, 0.90),
        ("mera", 1.00, 1.50),
    ])
    
    processor = LyricProcessor()
    units = processor.process_with_whisper_timestamps("tu hi mera", whisper_words)
    aligned = LyricAligner(config).align(units, notes)
    
    assert len(aligned) == 3
    # All words preserved
    assert [u.word for u in aligned] == ["tu", "hi", "mera"]
    # Note 0 overlaps both "tu" and "hi" - "hi" has stronger ownership (0.50 vs 0.39)
    # Note gets ONE primary owner: "hi"
    # "tu" has no primary-owned notes -> unmatched but preserved
    assert aligned[0].notes == []  # tu unmatched (no primary note)
    assert aligned[0].alignment_method == "whisper-unmatched"
    assert aligned[1].notes == [0]  # hi primary owner of note 0
    assert aligned[2].notes == [1]  # mera -> note 1


def test_whisper_word_no_note(config):
    """Word with no overlapping note should be preserved as unmatched."""
    notes = [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.10, end=0.40, duration=0.30, confidence=0.9),
    ]
    whisper_words = _whisper_words([
        ("hello", 0.50, 0.80),  # no overlap with note
    ])
    
    processor = LyricProcessor()
    units = processor.process_with_whisper_timestamps("hello", whisper_words)
    aligned = LyricAligner(config).align(units, notes)
    
    assert len(aligned) == 1
    assert aligned[0].word == "hello"
    assert aligned[0].notes == []  # no notes matched
    assert aligned[0].alignment_method == "whisper-unmatched"
    assert aligned[0].confidence == 0.0


def test_whisper_note_no_word(config):
    """Note with no overlapping word should be preserved (handled in pipeline)."""
    notes = [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.10, end=0.40, duration=0.30, confidence=0.9),
        DetectedNote(frequency=329.63, midi_note=64.0, start=0.50, end=0.80, duration=0.30, confidence=0.85),
    ]
    whisper_words = _whisper_words([
        ("tu", 0.10, 0.40),  # only overlaps note 0
    ])
    
    processor = LyricProcessor()
    units = processor.process_with_whisper_timestamps("tu", whisper_words)
    aligned = LyricAligner(config).align(units, notes)
    
    assert len(aligned) == 1
    assert aligned[0].notes == [0]  # only note 0
    # Note 1 has no lyric - this is verified in pipeline diagnostics


def test_whisper_slight_timestamp_mismatch(config):
    """20ms timing mismatch between Whisper and notes."""
    notes = [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.10, end=0.40, duration=0.30, confidence=0.9),
        DetectedNote(frequency=329.63, midi_note=64.0, start=0.40, end=0.70, duration=0.30, confidence=0.85),
    ]
    # Whisper has 20ms offset
    whisper_words = _whisper_words([
        ("tu", 0.12, 0.42),  # shifted by 20ms
        ("hi", 0.42, 0.72),
    ])
    
    processor = LyricProcessor()
    units = processor.process_with_whisper_timestamps("tu hi", whisper_words)
    aligned = LyricAligner(config).align(units, notes)
    
    assert len(aligned) == 2
    # Should still align correctly despite mismatch
    assert 0 in aligned[0].notes
    assert 1 in aligned[1].notes


def test_whisper_overlapping_lyric_timestamps(config):
    """Words with overlapping timestamps (rapid passage)."""
    notes = [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.10, end=0.35, duration=0.25, confidence=0.9),
        DetectedNote(frequency=329.63, midi_note=64.0, start=0.35, end=0.60, duration=0.25, confidence=0.85),
        DetectedNote(frequency=392.0, midi_note=67.0, start=0.60, end=0.85, duration=0.25, confidence=0.93),
    ]
    whisper_words = _whisper_words([
        ("tu", 0.10, 0.30),
        ("hi", 0.25, 0.55),  # overlaps with tu
        ("mera", 0.50, 0.85),
    ])
    
    processor = LyricProcessor()
    units = processor.process_with_whisper_timestamps("tu hi mera", whisper_words)
    aligned = LyricAligner(config).align(units, notes)
    
    assert len(aligned) == 3
    # All words preserved
    assert [u.word for u in aligned] == ["tu", "hi", "mera"]
    # Each should have primary ownership of their respective notes


def test_whisper_very_short_word(config):
    """Very short lyric word (consonant-like)."""
    notes = [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.10, end=0.40, duration=0.30, confidence=0.9),
        DetectedNote(frequency=329.63, midi_note=64.0, start=0.40, end=0.70, duration=0.30, confidence=0.85),
    ]
    whisper_words = _whisper_words([
        ("a", 0.10, 0.15),  # very short
        ("longword", 0.15, 0.70),
    ])
    
    processor = LyricProcessor()
    units = processor.process_with_whisper_timestamps("a longword", whisper_words)
    aligned = LyricAligner(config).align(units, notes)
    
    assert len(aligned) == 2
    assert aligned[0].word == "a"
    assert aligned[1].word == "longword"
    # Both preserved


def test_whisper_long_word(config):
    """Long lyric word spanning multiple notes."""
    notes = [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.10, end=0.40, duration=0.30, confidence=0.9),
        DetectedNote(frequency=293.66, midi_note=62.0, start=0.40, end=0.70, duration=0.30, confidence=0.85),
        DetectedNote(frequency=329.63, midi_note=64.0, start=0.70, end=1.00, duration=0.30, confidence=0.93),
    ]
    whisper_words = _whisper_words([
        ("loveeeee", 0.10, 1.00),  # spans all 3 notes
    ])
    
    processor = LyricProcessor()
    units = processor.process_with_whisper_timestamps("loveeeee", whisper_words)
    aligned = LyricAligner(config).align(units, notes)
    
    assert len(aligned) == 1
    assert aligned[0].word == "loveeeee"
    # Should own all 3 notes (melisma)
    assert len(aligned[0].notes) == 3
    assert set(aligned[0].notes) == {0, 1, 2}


def test_whisper_consecutive_words_no_gap(config):
    """Consecutive words with no gap between them."""
    notes = [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.10, end=0.35, duration=0.25, confidence=0.9),
        DetectedNote(frequency=329.63, midi_note=64.0, start=0.35, end=0.60, duration=0.25, confidence=0.85),
        DetectedNote(frequency=392.0, midi_note=67.0, start=0.60, end=0.85, duration=0.25, confidence=0.93),
    ]
    whisper_words = _whisper_words([
        ("I", 0.10, 0.35),
        ("love", 0.35, 0.60),
        ("you", 0.60, 0.85),
    ])
    
    processor = LyricProcessor()
    units = processor.process_with_whisper_timestamps("I love you", whisper_words)
    aligned = LyricAligner(config).align(units, notes)
    
    assert len(aligned) == 3
    assert aligned[0].notes == [0]
    assert aligned[1].notes == [1]
    assert aligned[2].notes == [2]


def test_whisper_empty_silent_regions(config):
    """Silent regions between words."""
    notes = [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.10, end=0.35, duration=0.25, confidence=0.9),
        DetectedNote(frequency=329.63, midi_note=64.0, start=0.50, end=0.75, duration=0.25, confidence=0.85),  # gap from 0.35-0.50
    ]
    whisper_words = _whisper_words([
        ("tu", 0.10, 0.35),
        ("hi", 0.50, 0.75),
    ])
    
    processor = LyricProcessor()
    units = processor.process_with_whisper_timestamps("tu hi", whisper_words)
    aligned = LyricAligner(config).align(units, notes)
    
    assert len(aligned) == 2
    assert aligned[0].notes == [0]
    assert aligned[1].notes == [1]


def test_whisper_dil_hai_bug(config):
    """Test for 'dil' + 'hai' where word boundary falls inside a note.
    
    Note 4 (1.30-1.60) spans the boundary between 'dil' (1.15-1.55) and 'hai' (1.55-1.90).
    'dil' has 83% ownership of note 4, 'hai' has only 17% (50ms overlap).
    Per requirements: 50ms boundary overlap should NOT assign note to both words.
    'dil' wins primary ownership of note 4; 'hai' is unmatched but preserved.
    """
    notes = [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.10, end=0.40, duration=0.30, confidence=0.9),  # S
        DetectedNote(frequency=293.66, midi_note=62.0, start=0.40, end=0.70, duration=0.30, confidence=0.85),  # R
        DetectedNote(frequency=329.63, midi_note=64.0, start=0.70, end=1.00, duration=0.30, confidence=0.93),  # G
        DetectedNote(frequency=349.23, midi_note=65.0, start=1.00, end=1.30, duration=0.30, confidence=0.8),  # P
        DetectedNote(frequency=392.0, midi_note=67.0, start=1.30, end=1.60, duration=0.30, confidence=0.9),  # D (note 4)
    ]
    # "dil" ends at 1.55, "hai" starts at 1.55 - both overlap note 4 (1.30-1.60)
    whisper_words = _whisper_words([
        ("dil", 1.15, 1.55),  # overlaps note 3 (1.00-1.30) and note 4 (1.30-1.60)
        ("hai", 1.55, 1.90),  # overlaps note 4 (only 50ms)
    ])
    
    processor = LyricProcessor()
    units = processor.process_with_whisper_timestamps("dil hai", whisper_words)
    aligned = LyricAligner(config).align(units, notes)
    
    assert len(aligned) == 2
    # Both words MUST survive (preserved even if unmatched)
    assert [u.word for u in aligned] == ["dil", "hai"]
    
    # "dil" primarily owns note 3 (50%) and note 4 (83%)
    assert 3 in aligned[0].notes  # dil owns note 3
    assert 4 in aligned[0].notes  # dil owns note 4 (strongest overlap)
    
    # "hai" has only 17% ownership of note 4 (below threshold) -> unmatched
    assert aligned[1].notes == []  # hai unmatched
    assert aligned[1].alignment_method == "whisper-unmatched"
    assert aligned[1].confidence == 0.0


def test_whisper_50ms_timing_mismatch(config):
    """50ms timing mismatch - should still align correctly."""
    notes = [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.10, end=0.40, duration=0.30, confidence=0.9),
        DetectedNote(frequency=329.63, midi_note=64.0, start=0.40, end=0.70, duration=0.30, confidence=0.85),
    ]
    whisper_words = _whisper_words([
        ("tu", 0.15, 0.45),  # 50ms late start
        ("hi", 0.45, 0.75),
    ])
    
    processor = LyricProcessor()
    units = processor.process_with_whisper_timestamps("tu hi", whisper_words)
    aligned = LyricAligner(config).align(units, notes)
    
    assert len(aligned) == 2
    assert aligned[0].notes == [0]
    assert aligned[1].notes == [1]


def test_whisper_100ms_timing_mismatch(config):
    """100ms timing mismatch - may cause unmatched but words preserved."""
    notes = [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.10, end=0.40, duration=0.30, confidence=0.9),
        DetectedNote(frequency=329.63, midi_note=64.0, start=0.40, end=0.70, duration=0.30, confidence=0.85),
    ]
    whisper_words = _whisper_words([
        ("tu", 0.20, 0.50),  # 100ms late
        ("hi", 0.50, 0.80),
    ])
    
    processor = LyricProcessor()
    units = processor.process_with_whisper_timestamps("tu hi", whisper_words)
    aligned = LyricAligner(config).align(units, notes)
    
    assert len(aligned) == 2
    # Words preserved even if alignment confidence is low
    assert aligned[0].word == "tu"
    assert aligned[1].word == "hi"
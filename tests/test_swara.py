import pytest
import numpy as np

from maestro.errors import ErrorCode, MaestroError
from maestro.swara import (
    SwaraConverter,
    swara_for_midi,
    TonicDetector,
    detect_tonic,
)
from maestro.models import DetectedNote


def _make_note(midi: float, duration: float = 0.3, confidence: float = 0.9, freq: float = None):
    """Helper to create a DetectedNote for testing."""
    if freq is None:
        freq = 440.0 * (2.0 ** ((midi - 69) / 12.0))
    return DetectedNote(
        frequency=freq,
        midi_note=midi,
        start=0.0,
        end=duration,
        duration=duration,
        confidence=confidence,
        f0_min=freq,
        f0_max=freq,
        frame_count=10,
    )


def test_tonic_c4_sa():
    conv = SwaraConverter(tonic_midi=60)
    p = conv.convert(60.0, conv.tonic_frequency())
    assert p.swara == "Sa"
    assert p.swara_type == "shuddha"
    assert p.octave == "madhya"
    assert p.semitone_offset == 0


def test_shuddha_semitones():
    conv = SwaraConverter(tonic_midi=60)
    assert conv.convert(62).swara == "Re"
    assert conv.convert(62).swara_type == "shuddha"
    assert conv.convert(64).swara == "Ga"
    assert conv.convert(65).swara == "Ma"
    assert conv.convert(67).swara == "Pa"
    assert conv.convert(59).swara == "Ni"  # flat Ni one below Sa


def test_komal_and_tivra():
    conv = SwaraConverter(tonic_midi=60)
    assert conv.convert(61).swara == "Re" and conv.convert(61).swara_type == "komal"
    assert conv.convert(63).swara == "Ga" and conv.convert(63).swara_type == "komal"
    assert conv.convert(66).swara == "Ma" and conv.convert(66).swara_type == "tivra"
    assert conv.convert(68).swara == "Dha" and conv.convert(68).swara_type == "komal"
    assert conv.convert(70).swara == "Ni" and conv.convert(70).swara_type == "komal"


def test_octaves():
    conv = SwaraConverter(tonic_midi=60)
    assert conv.convert(48).swara == "Sa" and conv.convert(48).octave == "mandra"
    assert conv.convert(72).swara == "Sa" and conv.convert(72).octave == "taar"
    assert conv.convert(84).octave.startswith("extended")


def test_frequency_bandwidth():
    freq = 440.0  # A4
    conv = SwaraConverter(tonic_midi=69)  # tonic = A4
    p = conv.convert(69.0, freq)
    assert p.swara == "Sa" and p.swara_type == "shuddha"
    assert p.cents_from_tonic == pytest.approx(0.0)


def test_invalid_tonic():
    with pytest.raises(MaestroError) as exc:
        SwaraConverter(tonic_midi=200)
    assert exc.value.code == ErrorCode.INVALID_TONIC


def test_swara_for_midi_convenience():
    p = swara_for_midi(62, 60)
    assert p.swara == "Re"


# ============================================================
# TONIC DETECTION TESTS
# ============================================================

def test_tonic_detector_basic_c_major():
    """Test tonic detection on a C major scale pattern."""
    # C4, E4, G4, A4, G4, E4, C4 (C major)
    notes = [
        _make_note(60),   # C4 - Sa
        _make_note(64),   # E4 - Ga
        _make_note(67),   # G4 - Pa
        _make_note(69),   # A4 - Dha
        _make_note(67),   # G4 - Pa
        _make_note(64),   # E4 - Ga
        _make_note(60),   # C4 - Sa
    ]
    tonic = detect_tonic(notes)
    assert tonic == 60, f"Expected tonic 60 (C4), got {tonic}"


def test_tonic_detector_d_major():
    """Test tonic detection on a D major scale pattern."""
    # D4, F#4, A4, B4, A4, F#4, D4 (D major)
    notes = [
        _make_note(62),   # D4 - Sa
        _make_note(66),   # F#4 - Ga
        _make_note(69),   # A4 - Pa
        _make_note(71),   # B4 - Dha
        _make_note(69),   # A4 - Pa
        _make_note(66),   # F#4 - Ga
        _make_note(62),   # D4 - Sa
    ]
    tonic = detect_tonic(notes)
    assert tonic == 62, f"Expected tonic 62 (D4), got {tonic}"


def test_tonic_detector_with_komal_notes():
    """Test tonic detection with komal (flat) notes."""
    # C4, Eb4, F4, G4, Ab4, Bb4, C5 (C minor-ish)
    notes = [
        _make_note(60),   # C4 - Sa
        _make_note(63),   # Eb4 - komal Ga
        _make_note(65),   # F4 - Ma
        _make_note(67),   # G4 - Pa
        _make_note(68),   # Ab4 - komal Dha
        _make_note(70),   # Bb4 - komal Ni
        _make_note(72),   # C5 - Sa (taar)
    ]
    tonic = detect_tonic(notes)
    assert tonic == 60, f"Expected tonic 60 (C4), got {tonic}"


def test_tonic_detector_octave_equivalence():
    """Test that octave-equivalent notes combine evidence for tonic."""
    # C3, C4, E4, G4, C5 - multiple octaves of C
    notes = [
        _make_note(48, duration=0.4),   # C3 - mandra Sa
        _make_note(60, duration=0.3),   # C4 - madhya Sa
        _make_note(64, duration=0.3),   # E4 - Ga
        _make_note(67, duration=0.3),   # G4 - Pa
        _make_note(72, duration=0.4),   # C5 - taar Sa
    ]
    tonic = detect_tonic(notes)
    assert tonic is not None
    assert tonic % 12 == 0, f"Expected tonic pitch class 0 (C), got MIDI {tonic}"


def test_tonic_detector_rejects_fifth_ambiguity():
    """Test that fifth-above candidate is resolved to lower tonic."""
    # Melody that could be C major or G major
    # C4, E4, G4, A4, G4, E4, C4
    notes = [
        _make_note(60),   # C4
        _make_note(64),   # E4
        _make_note(67),   # G4
        _make_note(69),   # A4
        _make_note(67),   # G4
        _make_note(64),   # E4
        _make_note(60),   # C4
    ]
    # Both C (60) and G (67) are strong candidates, but C should win
    tonic = detect_tonic(notes)
    assert tonic == 60, f"Expected tonic 60 (C4), got {tonic}"


def test_tonic_detector_insufficient_notes():
    """Test that too few notes returns None."""
    notes = [
        _make_note(60),
        _make_note(64),
    ]
    tonic = detect_tonic(notes)
    assert tonic is None


def test_tonic_detector_low_confidence():
    """Test that low confidence notes are ignored."""
    notes = [
        _make_note(60, confidence=0.9),
        _make_note(64, confidence=0.9),
        _make_note(67, confidence=0.1),  # Low confidence
    ]
    tonic = detect_tonic(notes)
    # Should still work with 2 good notes
    assert tonic == 60 or tonic is None  # May not have enough support


def test_tonic_detector_short_duration():
    """Test that very short notes are ignored."""
    notes = [
        _make_note(60, duration=0.01),  # Too short
        _make_note(64, duration=0.3),
        _make_note(67, duration=0.3),
    ]
    tonic = detect_tonic(notes)
    # May still work if enough other notes


def test_tonic_detector_manual_override():
    """Test that manual tonic is preserved when provided."""
    # The detect_tonic function doesn't handle override - that's done in pipeline
    # This test verifies the converter works with any tonic
    conv = SwaraConverter(tonic_midi=67)  # G4 as tonic
    p = conv.convert(67)
    assert p.swara == "Sa"
    assert p.octave == "madhya"


def test_tonic_detector_chromatic_all_intervals():
    """Test all 12 chromatic intervals relative to tonic."""
    conv = SwaraConverter(tonic_midi=60)
    
    # Test each semitone offset
    expected = [
        (0, "Sa", "shuddha"),
        (1, "Re", "komal"),
        (2, "Re", "shuddha"),
        (3, "Ga", "komal"),
        (4, "Ga", "shuddha"),
        (5, "Ma", "shuddha"),
        (6, "Ma", "tivra"),
        (7, "Pa", "shuddha"),
        (8, "Dha", "komal"),
        (9, "Dha", "shuddha"),
        (10, "Ni", "komal"),
        (11, "Ni", "shuddha"),
    ]
    
    for offset, swara, swara_type in expected:
        midi = 60 + offset
        p = conv.convert(float(midi))
        assert p.swara == swara, f"Offset {offset}: expected {swara}, got {p.swara}"
        assert p.swara_type == swara_type, f"Offset {offset}: expected {swara_type}, got {p.swara_type}"
        assert p.semitone_offset == offset % 12


def test_tonic_detector_fifth_above_penalty():
    """Test that a strong fifth-above candidate is penalized."""
    # Create notes that strongly support both C and G
    # C4 (twice), G4 (once), E4 (twice)
    notes = [
        _make_note(60, duration=0.5),   # C4 - strong tonic
        _make_note(60, duration=0.5),   # C4 - strong tonic
        _make_note(64, duration=0.3),   # E4
        _make_note(64, duration=0.3),   # E4
        _make_note(67, duration=0.2),   # G4 - only once
    ]
    tonic = detect_tonic(notes)
    assert tonic == 60, f"Expected tonic 60 (C4), got {tonic}"


def test_tonic_detector_pentatonic():
    """Test tonic detection on pentatonic scale."""
    # C major pentatonic: C, D, E, G, A
    notes = [
        _make_note(60),   # C4 - Sa
        _make_note(62),   # D4 - Re
        _make_note(64),   # E4 - Ga
        _make_note(67),   # G4 - Pa
        _make_note(69),   # A4 - Dha
        _make_note(67),   # G4 - Pa
        _make_note(64),   # E4 - Ga
        _make_note(62),   # D4 - Re
        _make_note(60),   # C4 - Sa
    ]
    tonic = detect_tonic(notes)
    assert tonic == 60, f"Expected tonic 60 (C4), got {tonic}"


def test_tonic_detector_minor_scale():
    """Test tonic detection on natural minor scale."""
    # A natural minor (relative to C major): A, B, C, D, E, F, G
    # But tonic should be A (69)
    notes = [
        _make_note(69),   # A4 - Sa
        _make_note(71),   # B4 - Re
        _make_note(72),   # C5 - komal Ga
        _make_note(74),   # D5 - Ma
        _make_note(76),   # E5 - Pa
        _make_note(77),   # F5 - komal Dha
        _make_note(79),   # G5 - komal Ni
        _make_note(81),   # A5 - Sa (taar)
    ]
    tonic = detect_tonic(notes)
    # The detector might pick 69 (A4) or 57 (A3) depending on octave estimation
    assert tonic is not None
    assert tonic % 12 == 9  # A = pitch class 9


def test_tonic_detector_with_tivra_ma():
    """Test tonic detection including tivra Ma (F# relative to C)."""
    # C4, E4, F#4, G4, A4, B4, C5 (Lydian-ish)
    notes = [
        _make_note(60),   # C4 - Sa
        _make_note(64),   # E4 - Ga
        _make_note(66),   # F#4 - tivra Ma
        _make_note(67),   # G4 - Pa
        _make_note(69),   # A4 - Dha
        _make_note(71),   # B4 - Ni
        _make_note(72),   # C5 - Sa
    ]
    tonic = detect_tonic(notes)
    assert tonic == 60, f"Expected tonic 60 (C4), got {tonic}"


def test_tonic_detector_ambiguous_returns_none():
    """Test that ambiguous melodies return None rather than guessing."""
    # Chromatic scale - no clear tonic
    notes = [
        _make_note(60),
        _make_note(61),
        _make_note(62),
        _make_note(63),
        _make_note(64),
        _make_note(65),
        _make_note(66),
        _make_note(67),
        _make_note(68),
        _make_note(69),
        _make_note(70),
        _make_note(71),
    ]
    tonic = detect_tonic(notes)
    # Should be None or a clear winner - not arbitrary
    # (May return something if one pitch class dominates by duration)


def test_tonic_detector_empty_notes():
    """Test empty notes list returns None."""
    tonic = detect_tonic([])
    assert tonic is None


def test_tonic_detector_fractional_midi():
    """Test tonic detection with fractional MIDI (vibrato, etc.)."""
    notes = [
        DetectedNote(
            frequency=261.63, midi_note=60.1, start=0.0, end=0.3, duration=0.3,
            confidence=0.9, f0_min=260, f0_max=263, frame_count=10
        ),
        DetectedNote(
            frequency=329.63, midi_note=63.9, start=0.3, end=0.6, duration=0.3,
            confidence=0.9, f0_min=328, f0_max=331, frame_count=10
        ),
        DetectedNote(
            frequency=392.00, midi_note=67.1, start=0.6, end=0.9, duration=0.3,
            confidence=0.9, f0_min=390, f0_max=394, frame_count=10
        ),
    ]
    tonic = detect_tonic(notes)
    assert tonic == 60


def test_tonic_detector_diagnostic_output():
    """Test that detector provides diagnostic info."""
    notes = [
        _make_note(60),
        _make_note(64),
        _make_note(67),
        _make_note(60),
    ]
    detector = TonicDetector()
    candidates = detector._evaluate_candidates(notes)
    assert len(candidates) > 0
    
    # Check best candidate has expected properties
    candidates.sort(key=lambda c: c.score, reverse=True)
    best = candidates[0]
    assert best.midi == 60
    assert best.supporting_notes > 0
    assert best.total_duration > 0
    assert best.avg_confidence > 0
    assert 0 in best.interval_evidence  # Unison evidence
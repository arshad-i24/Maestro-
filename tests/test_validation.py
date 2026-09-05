import math

import pytest

from maestro.models import DetectedNote, MaestroResult, SwaraOut
from maestro.validation import OutputValidator


def test_validate_notes_ok():
    notes = [
        DetectedNote(261.63, 60.0, 0.0, 0.5, 0.5, 0.9),
        DetectedNote(329.63, 64.0, 0.5, 1.0, 0.5, 0.8),
    ]
    OutputValidator().validate_notes(notes)


def test_validate_notes_bad_order():
    notes = [
        DetectedNote(329.63, 64.0, 0.6, 0.9, 0.3, 0.8),
        DetectedNote(261.63, 60.0, 0.0, 0.5, 0.5, 0.9),
    ]
    with pytest.raises(ValueError):
        OutputValidator().validate_notes(notes)


def test_validate_notes_bad_duration():
    notes = [DetectedNote(261.63, 60.0, 0.0, 0.1, -0.9, 0.9)]
    with pytest.raises(ValueError):
        OutputValidator().validate_notes(notes)


def make_result() -> MaestroResult:
    return MaestroResult(midi=None, swaras=[], lyrics=None)


def test_validate_result_nan_rejected():
    result = make_result()
    result.swaras = [
        SwaraOut(
            midi_note=math.nan, frequency=261.63, swara="Sa", swara_type="shuddha",
            octave="madhya", cents_from_tonic=0.0, start=0.0, end=0.4, duration=0.4, confidence=0.9,
        )
    ]
    with pytest.raises(ValueError):
        OutputValidator().validate_result(result)


def test_validate_result_bad_swara():
    result = make_result()
    result.swaras = [
        SwaraOut(
            midi_note=60.0, frequency=261.63, swara="Xy", swara_type="shuddha",
            octave="madhya", cents_from_tonic=0.0, start=0.0, end=0.4, duration=0.4, confidence=0.9,
        )
    ]
    with pytest.raises(ValueError):
        OutputValidator().validate_result(result)


def test_validate_midi_file_rejects_empty(tmp_path):
    path = tmp_path / "empty.mid"
    try:
        import mido

        mid = mido.MidiFile()
        mid.save(path)
    except Exception:
        path.write_bytes(b"")
    with pytest.raises(ValueError):
        OutputValidator().validate_midi_file(str(path))
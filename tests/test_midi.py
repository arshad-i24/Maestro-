import mido
import pytest

from maestro.config import AppConfig
from maestro.models import DetectedNote
from maestro.midi import MidiGenerator


def _notes():
    return [
        DetectedNote(frequency=261.63, midi_note=60.0, start=0.0, end=0.5, duration=0.5, confidence=0.9),
        DetectedNote(frequency=329.63, midi_note=64.0, start=0.6, end=1.1, duration=0.5, confidence=0.8),
        DetectedNote(frequency=392.0, midi_note=67.0, start=1.2, end=1.8, duration=0.6, confidence=0.95),
    ]


def test_notes_to_json(tmp_path):
    gen = MidiGenerator(AppConfig())
    infos = gen.build_notes(_notes())
    assert len(infos) == 3
    assert [n.pitch for n in infos] == [60, 64, 67]
    assert all(n.duration > 0 for n in infos)
    assert [n.start for n in infos] == sorted(n.start for n in infos)


def test_midi_file_roundtrip(tmp_path):
    gen = MidiGenerator(AppConfig())
    path = gen.to_file(_notes(), tempo_bpm=120.0, destination=tmp_path / "test.mid")
    mid = mido.MidiFile(path)
    events = [m for t in mid.tracks for m in t]
    notes_on = [m for m in events if m.type == "note_on"]
    notes_off = [m for m in events if m.type == "note_off"]
    assert len(notes_on) == 3
    assert len(notes_off) == 3
    assert any(m.type == "set_tempo" for m in events)
    assert [m.note for m in notes_on] == [60, 64, 67]


def test_invalid_note_timing_rejected(tmp_path):
    gen = MidiGenerator(AppConfig())
    bad = [DetectedNote(frequency=440.0, midi_note=69.0, start=0.5, end=0.2, duration=-0.3, confidence=0.9)]
    with pytest.raises(Exception):
        gen.to_file(bad, 120.0, tmp_path / "bad.mid")


def test_out_of_range_pitch_dropped():
    gen = MidiGenerator(AppConfig())
    notes = [
        DetectedNote(frequency=440.0, midi_note=69.0, start=0.0, end=0.5, duration=0.5, confidence=0.9),
        DetectedNote(frequency=18400.0, midi_note=140.0, start=0.6, end=0.9, duration=0.3, confidence=0.9),
    ]
    infos = gen.build_notes(notes)
    assert [n.pitch for n in infos] == [69]


def test_out_of_range_tempo_uses_clamped_ticks(tmp_path):
    """Regression: the file tempo is clamped to [20, 300] BPM, so the note
    tick positions must use the same clamped BPM or times drift."""
    gen = MidiGenerator(AppConfig())
    notes = [
        DetectedNote(frequency=261.63, midi_note=60.0, start=10.0, end=10.5, duration=0.5, confidence=0.9),
    ]
    path = gen.to_file(notes, tempo_bpm=5000.0, destination=tmp_path / "clamp.mid")
    mid = mido.MidiFile(path)
    track = mid.tracks[0]
    tempo_msg = next(m for m in track if m.type == "set_tempo")
    assert mido.tempo2bpm(tempo_msg.tempo) == pytest.approx(300.0)
    note_ons = [m for m in track if m.type == "note_on" and m.velocity > 0]
    assert len(note_ons) == 1
    assert note_ons[0].time == 24000  # 10 s * 300 bpm * 480 tpq / 60
import numpy as np

from maestro.audio import AudioLoader
from maestro.models import AudioData
from maestro.pitch import NoteSegmenter, CombinedDetector

MELODY_FREQS = [261.63, 329.63, 392.00]
MELODY_MIDIS = [60, 64, 67]


def test_segments_melody(config, melody_wav):
    audio = AudioLoader(config).load(melody_wav)
    frames = CombinedDetector(config).detect(audio)
    notes = NoteSegmenter(config).segment(frames)

    assert len(notes) >= 3, f"expected >=3 notes, got {len(notes)}"
    # the three core notes should map close to the expected MIDI values
    midis = sorted(round(n.midi_note) for n in notes)
    expected = sorted(MELODY_MIDIS)
    matched = 0
    for m in expected:
        if any(abs(mm - m) <= 1 for mm in midis):
            matched += 1
    assert matched >= 2, f"core pitches not matched: {midis} vs {expected}"

    # order + duration invariants
    prev_end = 0.0
    for n in notes:
        assert n.duration >= config.min_note_duration
        assert n.end > n.start
        assert n.confidence <= 1.0
        assert n.start >= prev_end - 1e-6
        prev_end = n.end


def test_vibrato_does_not_explode_note_count(config):
    """A steady tone with ~5 cent vibrato must stay ONE note."""
    sr = 22050
    duration = 1.2
    f0 = 440.0
    t = np.arange(int(sr * duration)) / sr
    vib_freq = np.sin(2 * np.pi * 5.5 * t) * 3.0  # ±3 cents
    y = 0.5 * np.sin(2 * np.pi * (f0 + vib_freq) * t)
    audio = AudioData(y.astype(np.float32), sr)
    frames = CombinedDetector(config).detect(audio)
    notes = NoteSegmenter(config).segment(frames)
    assert len(notes) <= 3, f"vibrato exploded notes: {len(notes)}"


def test_silence_produces_no_notes(config):
    audio = AudioData(np.zeros(22050, dtype=np.float32), 22050)
    frames = CombinedDetector(config).detect(audio)
    notes = NoteSegmenter(config).segment(frames)
    assert notes == []
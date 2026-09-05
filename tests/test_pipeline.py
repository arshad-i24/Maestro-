"""End-to-end pipeline tests on synthetic audio (no vocals separation)."""

import json

import pytest

from maestro.config import ProcessingOptions
from maestro.errors import ErrorCode, MaestroError
from maestro.pipeline import process_audio
from maestro.validation import OutputValidator, validate_dict_sections


def test_full_pipeline(config, melody_wav):
    opts = ProcessingOptions(
        lyrics="tu maana gaana hai",
        tonic=60,
        skip_separation=True,
    )
    result = process_audio(melody_wav, options=opts, config=config, job_id="e2e")

    # every required top-level section exists
    for section in ("metadata", "audio", "vocal_separation", "tempo", "pitch_analysis",
                    "midi", "swaras", "lyrics", "notation", "statistics", "warnings", "processing"):
        assert section in result.model_dump()

    assert result.audio.sample_rate == config.sample_rate
    assert result.midi.notes, "MIDI notes expected"
    assert result.midi.tempo > 0
    assert len(result.swaras) == len(result.midi.notes)
    assert result.lyrics.aligned is True
    assert len(result.lyrics.segments) >= 3
    assert len(result.notation) == len(result.midi.notes)
    assert result.statistics.total_seconds > 0
    assert result.processing["note_count"] == len(result.midi.notes)

    # validation passes cleanly
    OutputValidator().validate_result(result)
    validate_dict_sections(result.model_dump())
    midi_file = result.midi.file_path
    assert midi_file
    OutputValidator().validate_midi_file(midi_file)


def test_json_serializable(config, melody_wav):
    result = process_audio(
        melody_wav,
        options=ProcessingOptions(skip_separation=True, tonic=60),
        config=config,
    )
    dumped = json.dumps(result.model_dump(mode="json"))
    assert json.loads(dumped)["swaras"]  # round-trips


def test_tonic_controls_swaras(config, melody_wav):
    r1 = process_audio(melody_wav, options=ProcessingOptions(skip_separation=True, tonic=60), config=config)
    r2 = process_audio(melody_wav, options=ProcessingOptions(skip_separation=True, tonic=62), config=config)
    # same audio, different Sa => the swara (or its octave) must react to the tonic
    assert r1.swaras[0].midi_note == pytest.approx(r2.swaras[0].midi_note)
    assert (r1.swaras[0].swara, r1.swaras[0].octave) != (r2.swaras[0].swara, r2.swaras[0].octave)
    # interval is preserved: cents_from_tonic shifts by exactly the Sa difference
    assert r2.swaras[0].cents_from_tonic == pytest.approx(r1.swaras[0].cents_from_tonic - 2400.0)


def test_no_notes_error(config, tmp_path):
    import numpy as np
    import soundfile as sf

    silent = tmp_path / "silent.wav"
    sf.write(silent, np.zeros(22050, dtype=np.float32), 22050)
    with pytest.raises(MaestroError) as exc:
        process_audio(silent, options=ProcessingOptions(skip_separation=True), config=config)
    assert exc.value.code == ErrorCode.NO_NOTES_DETECTED


def test_note_name_tonic(config, melody_wav):
    result = process_audio(melody_wav, tonic="C4", options=ProcessingOptions(skip_separation=True), config=config)
    assert result.swaras  # parses fine


def test_invalid_tonic_raises_structured(config, melody_wav):
    with pytest.raises(MaestroError) as exc:
        process_audio(melody_wav, tonic="not-a-note", config=config)
    assert exc.value.code == ErrorCode.INVALID_TONIC


def test_auto_lyrics_from_vocals(config, melody_wav, monkeypatch):
    from maestro import pipeline as pipeline_mod

    class FakeGenerator:
        def __init__(self, *args, **kwargs):
            pass

        @staticmethod
        def transcribe(audio, conf=None):
            assert audio.samples.size > 0
            return "tu maana gaana hai"

    monkeypatch.setattr(pipeline_mod, "generate_lyrics", FakeGenerator.transcribe)

    result = process_audio(
        melody_wav,
        options=ProcessingOptions(skip_separation=True, tonic=60, transcribe_lyrics=True),
        config=config,
    )

    assert result.lyrics.aligned is True
    assert result.lyrics.source == "whisper"
    assert [s.word for s in result.lyrics.segments] == ["tu", "maana", "gaana", "hai"]
    assert any(entry.lyric for entry in result.notation)
    assert any(w.code == "LYRICS_AUTO" for w in result.warnings)
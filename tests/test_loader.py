import pytest

from maestro.audio import AudioLoader, SUPPORTED_FORMATS
from maestro.errors import ErrorCode, MaestroError


def test_supported_formats():
    assert ".wav" in SUPPORTED_FORMATS
    assert ".mp3" in SUPPORTED_FORMATS
    assert ".flac" in SUPPORTED_FORMATS
    assert ".m4a" in SUPPORTED_FORMATS


def test_load_wav(config, sine_wav):
    audio = AudioLoader(config).load(sine_wav)
    assert audio.sample_rate == config.sample_rate
    assert audio.duration == pytest.approx(1.0, abs=0.05)
    assert audio.channels_at_load == 1
    assert audio.peak_amplitude >= 0.49  # generated sine at amplitude 0.5


def test_missing_file(config):
    with pytest.raises(MaestroError) as exc:
        AudioLoader(config).load(str(config.input_dir) + "/nope.wav")
    assert exc.value.code == ErrorCode.INVALID_AUDIO


def test_unsupported_format(config, tmp_path):
    bad = tmp_path / "song.txt"
    bad.write_text("hello")
    with pytest.raises(MaestroError) as exc:
        AudioLoader(config).load(bad)
    assert exc.value.code == ErrorCode.UNSUPPORTED_FORMAT


def test_empty_file(config, empty_wav):
    with pytest.raises(MaestroError) as exc:
        AudioLoader(config).load(empty_wav)
    assert exc.value.code == ErrorCode.AUDIO_EMPTY


def test_short_file(config, short_wav):
    with pytest.raises(MaestroError) as exc:
        AudioLoader(config).load(short_wav)
    assert exc.value.code == ErrorCode.AUDIO_TOO_SHORT


def test_long_file(config, tmp_path):
    import numpy as np
    import soundfile as sf

    path = tmp_path / "long.wav"
    y = np.zeros(int(config.max_duration_seconds * config.sample_rate) + 1, dtype=np.float32)
    sf.write(path, y.astype(np.float32), config.sample_rate)
    with pytest.raises(MaestroError) as exc:
        AudioLoader(config).load(path)
    assert exc.value.code == ErrorCode.AUDIO_TOO_LONG


def test_corrupt_file(config, corrupt_wav):
    with pytest.raises(MaestroError) as exc:
        AudioLoader(config).load(corrupt_wav)
    assert exc.value.code == ErrorCode.INVALID_AUDIO
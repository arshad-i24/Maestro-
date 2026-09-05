import numpy as np
import pytest

from maestro.audio import AudioPreprocessor
from maestro.models import AudioData

def _audio(samples, sr=22050):
    return AudioData(np.asarray(samples, dtype=np.float32), sr)


def test_to_mono(config):
    stereo = np.stack([np.ones(1000), 2 * np.ones(1000)], axis=1)
    proc = AudioPreprocessor(config)
    mono = proc.to_mono(stereo)
    assert mono.shape == (1000,)
    assert np.allclose(mono, 1.5)


def test_normalize_peak(config):
    x = np.linspace(-0.3, 0.3, 100)
    out = AudioPreprocessor(config).normalize(x, peak=0.9)
    assert np.max(np.abs(out)) == pytest.approx(0.9)


def test_remove_dc(config):
    x = np.full(200, 5.0, dtype=np.float64)
    out = AudioPreprocessor(config).remove_dc(x)
    assert np.allclose(out, 0.0, atol=1e-9)


def test_trim_edges_removes_silence(config):
    silence = np.zeros(int(0.2 * 22050), dtype=np.float64)
    tone = 0.5 * np.sin(2 * np.pi * 440 * np.arange(22050) / 22050)
    x = np.concatenate([silence, tone, silence])
    prec = AudioPreprocessor(config)
    trimmed = prec.trim_edges(x, 22050)
    assert len(trimmed) < len(x)
    assert len(trimmed) >= len(tone)


def test_process_pipeline(config):
    x = np.concatenate([np.zeros(500), 0.4 * np.sin(2 * np.pi * 440 * np.arange(6000) / 22050)])
    out = AudioPreprocessor(config).process(_audio(x))
    assert out.samples.ndim == 1
    assert np.max(np.abs(out.samples)) <= 1.0


def test_frame_rms_db(config):
    x = 0.1 * np.ones(512 * 10)
    db = AudioPreprocessor(config).frame_rms_db(x, 22050, 512)
    assert len(db) == 10
    assert np.all(db < 0) and np.all(db > -60)
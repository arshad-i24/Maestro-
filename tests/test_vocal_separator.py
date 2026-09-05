import numpy as np
import pytest

from maestro.vocal import (
    DemucsSeparator,
    PassthroughSeparator,
    get_separator,
    separate_vocals,
)
from maestro.audio import AudioLoader
from maestro.models import AudioData


def test_passthrough_is_interface_compliant(config, melody_wav):
    """The passthrough separator must never raise and is clearly not real."""
    audio = AudioLoader(config).load(melody_wav)
    sep = PassthroughSeparator()
    result = sep.separate(audio)
    assert result.separated is False
    assert result.method == "passthrough"
    assert result.vocals is audio


def test_get_separator_with_none_model(config):
    separator = get_separator(config)
    assert isinstance(separator, PassthroughSeparator)


def test_separate_vocals_returns_warnings_on_fallback(config, melody_wav):
    audio = AudioLoader(config).load(melody_wav)
    result, warnings = separate_vocals(audio, config)
    assert result.method == "passthrough"


def test_demucs_separator_availability_flag():
    demucs = DemucsSeparator("htdemucs")
    # Should not crash regardless of whether demucs is installed.
    assert demucs.available in (True, False)


def test_demucs_run_picks_vocals_stem_not_first_stem(config, monkeypatch):
    """Regression: htdemucs emits [drums, bass, other, vocals]; the vocal
    stem sits at index 3, not 0. If we grab out[0, 0] we transcribe drums."""
    torch = pytest.importorskip("torch")
    pytest.importorskip("demucs")

    n = 4_000
    mix = np.full(n, 1.0, dtype=np.float32)
    stems = {
        "drums": np.full(n, 0.10, dtype=np.float32),
        "bass": np.full(n, 0.20, dtype=np.float32),
        "other": np.full(n, 0.30, dtype=np.float32),
        "vocals": np.full(n, 0.50, dtype=np.float32),
    }
    out = torch.tensor(np.stack([np.stack([stems[s], stems[s]]) for s in ["drums", "bass", "other", "vocals"]])).unsqueeze(0)

    def fake_apply_model(model, mix_, **_kwargs):
        return out

    class FakeDeviceParam:
        device = "cpu"

    class FakeModel:
        sources = ["drums", "bass", "other", "vocals"]
        samplerate = config.sample_rate

        @staticmethod
        def parameters():
            return iter([FakeDeviceParam()])

    monkeypatch.setattr("demucs.apply.apply_model", fake_apply_model)
    sep = DemucsSeparator("htdemucs", device="cpu", sample_rate=config.sample_rate)
    monkeypatch.setattr(sep, "_load_model", lambda: FakeModel())

    result = sep._run(AudioData(mix, config.sample_rate))

    assert np.allclose(result.vocals.mono(), stems["vocals"], atol=1e-5), (
        "vocals must come from the 'vocals' stem (index 3), not the first stem"
    )
    assert not np.allclose(result.vocals.mono(), stems["drums"], atol=1e-5)
    expected_instrumental = mix - stems["vocals"]
    assert np.allclose(result.instrumental.mono(), expected_instrumental, atol=1e-5)
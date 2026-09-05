import pytest

from maestro.audio import AudioLoader
from maestro.pitch import (
    CombinedDetector,
    PyinDetector,
    StftDetector,
    create_pitch_detector,
)


def test_create_detector_default(config):
    detector = create_pitch_detector(config.pitch_detection_method, config)
    assert isinstance(detector, PyinDetector) or isinstance(detector, CombinedDetector)


def test_create_detector_stft(config):
    assert isinstance(create_pitch_detector("stft", config), StftDetector)


def test_pyin_finds_440(config, sine_wav):
    audio = AudioLoader(config).load(sine_wav)
    frames = PyinDetector(config).detect(audio)
    voiced = [f for f in frames if f.voiced and f.confidence > 0.5]
    assert len(voiced) > 10, "expected many voiced frames on a pure tone"
    freqs = [f.frequency for f in voiced]
    mean_freq = sum(freqs) / len(freqs)
    assert 430 < mean_freq < 450
    assert all(f.midi_note and 68 < f.midi_note < 70 for f in voiced)


def test_stft_finds_440(config, sine_wav):
    audio = AudioLoader(config).load(sine_wav)
    frames = StftDetector(config).detect(audio)
    voiced = [f for f in frames if f.voiced]
    assert voiced, "stft detector found nothing"
    freqs = [f.frequency for f in voiced]
    mean_freq = sum(freqs) / len(freqs)
    assert abs(mean_freq - 440.0) < 15.0


def test_silence_gives_unvoiced_frames(config):
    import numpy as np

    from maestro.models import AudioData

    audio = AudioData(np.zeros(22050, dtype=np.float32), 22050)
    frames = CombinedDetector(config).detect(audio)
    assert all(not f.voiced for f in frames)


def test_detector_raises_structured(config, tmp_path):
    import numpy as np

    from maestro.models import AudioData

    audio = AudioData(np.zeros(22050, dtype=np.float32), 22050)
    # pyin on silence should still not raise
    frames = PyinDetector(config).detect(audio)
    assert isinstance(frames, list)
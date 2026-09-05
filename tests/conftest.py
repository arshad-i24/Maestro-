"""Shared fixtures: synthetic audio + isolated engine config.

All tests use generated sine-wave audio so nothing large needs downloading.
The engine configuration is pointed at the test's tmp dir to avoid writing
artifacts into the repo.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from maestro.config import AppConfig


def make_sine(
    path: Path,
    frequency: float,
    duration: float,
    sr: int = 22050,
    amplitude: float = 0.5,
) -> Path:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    y = (amplitude * np.sin(2 * np.pi * frequency * t)).astype(np.float32)
    sf.write(path, y, sr)
    return path


def make_melody(
    path: Path,
    freqs: list[float],
    note_len: float = 0.30,
    gap: float = 0.08,
    sr: int = 22050,
    amplitude: float = 0.5,
) -> Path:
    """Chain *freqs* with silent gaps between them (pure sine tones)."""
    chunks = []
    for freq in freqs:
        n = int(sr * note_len)
        t = np.arange(n) / sr
        chunks.append((amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32))
        chunks.append(np.zeros(int(sr * gap), dtype=np.float32))
    y = np.concatenate(chunks)
    sf.write(path, y, sr)
    return path


MELODY_FREQS = [261.63, 329.63, 392.00]  # C4, E4, G4
MELODY_MIDIS = [60, 64, 67]


@pytest.fixture()
def config(tmp_path: Path) -> AppConfig:
    """An AppConfig isolated to a temp directory with passthrough vocals."""
    return AppConfig(
        sample_rate=22050,
        output_dir=str(tmp_path / "output"),
        input_dir=str(tmp_path / "input"),
        vocal_separation_model="none",
        device="cpu",
        keep_stems=False,
        min_duration_seconds=0.05,
        max_duration_seconds=120.0,
        min_note_duration=0.06,
        onset_threshold_frames=4,
        smoothing_window=5,
    )


@pytest.fixture()
def sine_wav(tmp_path: Path) -> Path:
    return make_sine(tmp_path / "sine440.wav", 440.0, 1.0)


@pytest.fixture()
def melody_wav(tmp_path: Path) -> Path:
    return make_melody(tmp_path / "melody.wav", MELODY_FREQS)


@pytest.fixture()
def empty_wav(tmp_path: Path) -> Path:
    path = tmp_path / "empty.wav"
    sf.write(path, np.zeros(0, dtype=np.float32), 22050)
    return path


@pytest.fixture()
def short_wav(tmp_path: Path) -> Path:
    return make_sine(tmp_path / "short.wav", 440.0, 0.01)


@pytest.fixture()
def corrupt_wav(tmp_path: Path) -> Path:
    path = tmp_path / "corrupt.wav"
    path.write_bytes(b"this is not a valid wave file at all" * 100)
    return path
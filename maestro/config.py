"""Engine configuration.

AppConfig: all tuneable knobs for the Maestro engine (audio, pitch, MIDI,
vocal separation, etc.). ProcessingOptions: per-request overrides sent by
the caller (tonic, lyrics, skip flags, tempo).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AppConfig:
    # --- audio ----------------------------------------------------------------
    sample_rate: int = 22050
    min_duration_seconds: float = 0.1
    max_duration_seconds: float = 600.0
    amp_normalize_peak: float = 0.9
    trim_silence: bool = True
    silence_threshold_db: float = -40.0

    # --- pitch detection ------------------------------------------------------
    pitch_detection_method: str = "pyin"  # "pyin" | "stft" | "combined"
    fmin_hz: float = 65.0
    fmax_hz: float = 2100.0
    frame_length: int = 2048
    hop_length: int = 512

    # --- note segmentation ----------------------------------------------------
    pitch_tolerance_semitones: float = 0.6
    note_confidence_threshold: float = 0.3
    min_note_duration: float = 0.06
    onset_threshold_frames: int = 4
    smoothing_window: int = 5

    # --- MIDI -----------------------------------------------------------------
    midi_ticks_per_beat: int = 480
    midi_program: int = 0  # Acoustic Grand Piano
    midi_channel: int = 0
    midi_velocity: int = 80
    default_tempo_bpm: float = 120.0

    # --- vocal separation -----------------------------------------------------
    vocal_separation_model: str = "htdemucs"
    device: str = "cpu"
    model_dir: str = ""
    reuse_models: bool = True
    keep_stems: bool = False

    # --- lyric transcription (auto-generate lyrics via Whisper) --------------
    lyric_asr_model: str = "small"
    lyric_asr_compute_type: str = "int8"

    # --- paths ----------------------------------------------------------------
    output_dir: str = "output"
    input_dir: str = "input"


@dataclass
class ProcessingOptions:
    """Per-request overrides (passed to ``process_audio``)."""

    tonic: Optional[int | str] = 60
    lyrics: Optional[str] = None
    skip_separation: bool = False
    vocals_only: bool = False
    tempo_bpm: Optional[float] = None
    keep_stems: bool = False
    transcribe_lyrics: bool = False


def get_config() -> AppConfig:
    """Return the default engine configuration."""
    return AppConfig()

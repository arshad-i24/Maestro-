"""Data models for the Maestro engine.

Two layers:
* **Internal dataclasses** — AudioData, PitchFrame, DetectedNote … (NumPy payloads).
* **Output/API Pydantic models** — stable JSON schema (MaestroResult etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Internal dataclasses (NumPy payloads)
# ---------------------------------------------------------------------------


@dataclass
class AudioData:
    """Canonical internal audio representation.

    ``samples`` is always monophonic float32 in range roughly [-1, 1].
    """

    samples: np.ndarray
    sample_rate: int
    path: Optional[str] = None
    original_sample_rate: Optional[int] = None
    channels_at_load: int = 1
    duration: float = 0.0
    peak_amplitude: float = 0.0

    def __post_init__(self) -> None:
        self.samples = np.asarray(self.samples, dtype=np.float32)
        if self.samples.ndim == 2 and self.channels_at_load == 1:
            self.channels_at_load = int(self.samples.shape[1])
        if self.samples.ndim == 2:
            self.samples = self.samples.mean(axis=1).astype(np.float32)
        elif self.samples.ndim != 1:
            self.samples = self.samples.reshape(-1)
        if self.sample_rate > 0 and self.samples.size:
            self.duration = float(self.samples.size) / self.sample_rate
            self.peak_amplitude = float(np.max(np.abs(self.samples))) if self.samples.size else 0.0

    def mono(self) -> np.ndarray:
        return self.samples


@dataclass
class PitchFrame:
    """One frame of f0 estimation."""

    time: float
    frequency: Optional[float]
    voiced: bool
    confidence: float
    midi_note: Optional[float] = None


@dataclass
class DetectedNote:
    """A segmented musical note."""

    frequency: float
    midi_note: float
    start: float
    end: float
    duration: float
    confidence: float
    f0_min: float = 0.0
    f0_max: float = 0.0
    frame_count: int = 0


@dataclass
class SeparationResult:
    """Output of the vocal separation stage."""

    vocals: AudioData
    instrumental: Optional[AudioData] = None
    method: str = "passthrough"
    model: Optional[str] = None
    device: Optional[str] = None
    separated: bool = False
    vocals_path: Optional[str] = None
    instrumental_path: Optional[str] = None
    # Diagnostics
    vocal_rms: float = 0.0
    vocal_peak: float = 0.0
    vocal_duration: float = 0.0
    instrumental_rms: float = 0.0


@dataclass
class LyricUnit:
    """A token of lyric text (word)."""

    word: str
    index: int
    start: Optional[float] = None
    end: Optional[float] = None
    syllables: list[str] = field(default_factory=list)
    notes: list[int] = field(default_factory=list)
    confidence: float = 0.0
    alignment_method: str = "time-proportional"
    # Whisper word timestamps (if available)
    whisper_start: Optional[float] = None
    whisper_end: Optional[float] = None
    whisper_confidence: Optional[float] = None


# ---------------------------------------------------------------------------
# Output / API models (Pydantic) — stable JSON schema
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class MidiNoteOut(BaseModel):
    pitch: int = Field(ge=0, le=127)
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    duration: float = Field(gt=0)


class DetectedNoteOut(BaseModel):
    midi_note: float
    frequency: float
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    duration: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)


class MidiInfoOut(BaseModel):
    tempo: float = Field(gt=0)
    ticks_per_beat: int = 480
    notes: list[MidiNoteOut]
    file_path: Optional[str] = None


class SwaraOut(BaseModel):
    midi_note: float
    frequency: float
    swara: str
    swara_type: str
    octave: str
    cents_from_tonic: float
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    duration: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)


class NoteRefOut(BaseModel):
    swara: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    midi_note: float
    frequency: float


class LyricSegmentOut(BaseModel):
    word: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    alignment_method: str
    notes: list[NoteRefOut] = Field(default_factory=list)


class NotationEntryOut(BaseModel):
    swara: str
    octave: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    duration: float = Field(gt=0)
    lyric: Optional[str] = None
    confidence: float = Field(ge=0, le=1)
    symbol: str = ""


class PitchStatsOut(BaseModel):
    frames_analyzed: int = 0
    voiced_frames: int = 0
    fundamental_freq_mean: Optional[float] = None
    fundamental_freq_min: Optional[float] = None
    fundamental_freq_max: Optional[float] = None


class AudioInfoOut(BaseModel):
    file_path: str
    format: str
    sample_rate: int
    channels: int
    duration: float
    peak_amplitude: float


class VocalSeparationOut(BaseModel):
    performed: bool
    method: str = "passthrough"
    model: Optional[str] = None
    device: Optional[str] = None
    vocals_path: Optional[str] = None
    instrumental_path: Optional[str] = None
    vocal_rms: float = 0.0
    vocal_peak: float = 0.0
    vocal_duration: float = 0.0
    instrumental_rms: float = 0.0


class TempoOut(BaseModel):
    bpm: Optional[float] = None
    source: str = "estimated"


class MetadataOut(BaseModel):
    engine: str = "maestro"
    version: str = "0.1.0"
    timestamp: str = Field(default_factory=_utcnow)
    input_format: Optional[str] = None
    tonic_midi: Optional[int] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class WarningOut(BaseModel):
    code: str
    message: str
    stage: Optional[str] = None


class ProcessingStatsOut(BaseModel):
    total_seconds: float = Field(default=0.0, ge=0)
    stages: dict[str, float] = Field(default_factory=dict)


class WordTimestampOut(BaseModel):
    word: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)


class LyricsOut(BaseModel):
    aligned: bool
    source: str = "none"
    confidence: float = Field(ge=0, le=1)
    segments: list[LyricSegmentOut] = Field(default_factory=list)
    word_timestamps: list[WordTimestampOut] = Field(default_factory=list)


class MaestroResult(BaseModel):
    """Top-level JSON schema returned by the pipeline."""

    model_config = ConfigDict(extra="allow")

    metadata: dict[str, Any] = Field(default_factory=dict)
    audio: Optional[AudioInfoOut] = None
    vocal_separation: Optional[VocalSeparationOut] = None
    tempo: Optional[TempoOut] = None
    pitch_analysis: Optional[PitchStatsOut] = None
    midi: Optional[MidiInfoOut] = None
    swaras: list[SwaraOut] = Field(default_factory=list)
    lyrics: Optional[LyricsOut] = None
    notation: list[NotationEntryOut] = Field(default_factory=list)
    statistics: Optional[ProcessingStatsOut] = None
    warnings: list[WarningOut] = Field(default_factory=list)
    processing: dict[str, Any] = Field(default_factory=dict)

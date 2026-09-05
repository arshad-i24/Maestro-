"""MIDI generation and vocal transcription orchestration.

MidiGenerator: converts detected notes to a Standard MIDI File via mido.
VocalTranscriber: chains pitch detection → note segmentation → MIDI generation
  with tempo estimation and profiling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from .config import AppConfig
from .errors import ErrorCode, MaestroError
from .models import AudioData, DetectedNote, MidiInfoOut, MidiNoteOut, PitchStatsOut
from .pitch import NoteSegmenter, create_pitch_detector

logger = logging.getLogger("maestro.midi")


# ---------------------------------------------------------------------------
# MIDI Generator
# ---------------------------------------------------------------------------


class MidiGenerator:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def build_notes(self, notes: list[DetectedNote]) -> list[MidiNoteOut]:
        out: list[MidiNoteOut] = []
        for n in notes:
            pitch = _round_midi(n.midi_note)
            if not 0 <= pitch <= 127:
                continue
            if not (n.end >= n.start and n.duration > 0):
                raise MaestroError(
                    ErrorCode.MIDI_GENERATION_FAILED,
                    f"Invalid note timing for MIDI: start={n.start} end={n.end}",
                )
            out.append(
                MidiNoteOut(
                    pitch=pitch,
                    start=round(float(n.start), 6),
                    end=round(float(n.end), 6),
                    duration=round(float(n.duration), 6),
                )
            )
        out.sort(key=lambda m: (m.start, m.end))
        return out

    def to_file(
        self,
        notes: list[DetectedNote],
        tempo_bpm: float,
        destination: str | Path,
    ) -> str:
        try:
            import mido
        except ImportError as exc:
            raise MaestroError(
                ErrorCode.MIDI_GENERATION_FAILED,
                "mido is required for MIDI generation",
            ) from exc

        midi_notes = self.build_notes(notes)
        ticks_per_beat = self.config.midi_ticks_per_beat
        mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
        track = mido.MidiTrack()
        mid.tracks.append(track)

        clamped_bpm = min(300.0, max(20.0, tempo_bpm))
        tempo_us_per_beat = int(mido.bpm2tempo(clamped_bpm))
        track.append(mido.MetaMessage("set_tempo", tempo=tempo_us_per_beat, time=0))
        track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
        track.append(mido.Message("program_change", program=self.config.midi_program, time=0))

        def to_ticks(seconds: float) -> int:
            return int(round(seconds * clamped_bpm * ticks_per_beat / 60.0))

        prev_ticks = 0
        channel = self.config.midi_channel
        for note in midi_notes:
            start_ticks = to_ticks(note.start)
            end_ticks = to_ticks(note.end)
            track.append(
                mido.Message(
                    "note_on",
                    note=note.pitch,
                    velocity=self.config.midi_velocity,
                    time=start_ticks - prev_ticks,
                    channel=channel,
                )
            )
            track.append(
                mido.Message(
                    "note_off",
                    note=note.pitch,
                    velocity=0,
                    time=max(1, end_ticks - start_ticks),
                    channel=channel,
                )
            )
            prev_ticks = start_ticks

        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        mid.save(str(dest))
        return str(dest)

    def build_info(
        self,
        notes: list[DetectedNote],
        tempo_bpm: float,
        file_path: Optional[str] = None,
    ) -> MidiInfoOut:
        return MidiInfoOut(
            tempo=round(float(tempo_bpm), 4),
            ticks_per_beat=self.config.midi_ticks_per_beat,
            notes=self.build_notes(notes),
            file_path=file_path,
        )


def _round_midi(midi: float) -> int:
    return int(round(midi))


# ---------------------------------------------------------------------------
# Transcription Orchestrator
# ---------------------------------------------------------------------------


@dataclass
class TranscriptionResult:
    notes: list[DetectedNote]
    midi_info: MidiInfoOut
    pitch_stats: PitchStatsOut
    tempo_bpm: float
    tempo_source: str


class Profiler:
    """Small helper to time pipeline stages."""

    def __init__(self) -> None:
        self._t0: Optional[float] = None
        self.stages: dict[str, float] = {}

    def start(self) -> None:
        import time
        self._t0 = time.perf_counter()

    def mark(self, stage: str) -> None:
        import time
        now = time.perf_counter()
        if self._t0 is not None:
            self.stages[stage] = round(now - self._t0, 4)
            self._t0 = now


class VocalTranscriber:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.pitch_detector = create_pitch_detector(config.pitch_detection_method, config)
        self.segmenter = NoteSegmenter(config)
        self.midi = MidiGenerator(config)

    def transcribe(self, vocals: AudioData, tempo_bpm: Optional[float] = None) -> TranscriptionResult:
        try:
            frames = self.pitch_detector.detect(vocals)
        except MaestroError:
            raise
        except Exception as exc:
            raise MaestroError(
                ErrorCode.PITCH_DETECTION_FAILED,
                f"pitch detection crashed: {exc}",
            ) from exc

        try:
            notes = self.segmenter.segment(frames)
        except Exception as exc:
            raise MaestroError(
                ErrorCode.NOTE_SEGMENTATION_FAILED,
                f"note segmentation crashed: {exc}",
            ) from exc

        bpm, source = self._estimate_tempo(vocals, tempo_bpm)

        try:
            midi_info = self.midi.build_info(notes, bpm)
        except MaestroError:
            raise
        except Exception as exc:
            raise MaestroError(
                ErrorCode.MIDI_GENERATION_FAILED,
                f"midi generation crashed: {exc}",
            ) from exc

        stats = self._pitch_stats(frames, notes)
        return TranscriptionResult(
            notes=notes,
            midi_info=midi_info,
            pitch_stats=stats,
            tempo_bpm=bpm,
            tempo_source=source,
        )

    def _estimate_tempo(self, vocals: AudioData, explicit: Optional[float]) -> tuple[float, str]:
        if explicit is not None and 20.0 <= explicit <= 300.0:
            return float(explicit), "provided"
        try:
            try:
                from librosa.feature.rhythm import tempo as _tempo
            except ImportError:
                import librosa
                _tempo = librosa.beat.tempo
            tempos = _tempo(
                y=np.asarray(vocals.mono(), dtype=np.float64),
                sr=vocals.sample_rate,
            )
            bpm = float(np.median(tempos))
            if 40.0 <= bpm <= 220.0:
                return round(bpm, 2), "estimated"
        except Exception:
            logger.debug("tempo estimation failed; using default")
        return self.config.default_tempo_bpm, "default"

    @staticmethod
    def _pitch_stats(frames, notes: list[DetectedNote]) -> PitchStatsOut:
        freqs = [f.frequency for f in frames if f.frequency is not None and f.frequency > 0]
        return PitchStatsOut(
            frames_analyzed=len(frames),
            voiced_frames=len(freqs),
            fundamental_freq_mean=round(float(np.mean(freqs)), 2) if freqs else None,
            fundamental_freq_min=round(float(np.min(freqs)), 2) if freqs else None,
            fundamental_freq_max=round(float(np.max(freqs)), 2) if freqs else None,
        )

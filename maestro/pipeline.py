"""Maestro unified pipeline.

process_audio() runs the full chain and returns a validated MaestroResult::

    audio → preprocessing → [vocal separation] → vocal preprocessing →
    pitch detection → note segmentation → MIDI → swaras → lyrics alignment →
    notation → JSON
"""

from __future__ import annotations

import json
import logging
import time as _time
from pathlib import Path
from typing import Optional, Union

from . import __version__
from .audio import AudioLoader, AudioPreprocessor
from .config import AppConfig, ProcessingOptions, get_config
from .errors import ErrorCode, MaestroError
from .lyrics import LyricAligner, LyricProcessor
from .lyric_asr import generate_lyrics
from .midi import Profiler, VocalTranscriber
from .models import (
    AudioInfoOut,
    DetectedNote,
    LyricSegmentOut,
    LyricsOut,
    MaestroResult,
    MetadataOut,
    NoteRefOut,
    ProcessingStatsOut,
    SwaraOut,
    TempoOut,
    VocalSeparationOut,
    WarningOut,
)
from .notation import NotationGenerator
from .swara import SwaraConverter, note_name_to_midi
from .validation import OutputValidator
from .vocal import PassthroughSeparator, separate_vocals

logger = logging.getLogger("maestro.pipeline")


def process_audio(
    audio_path,
    lyrics: Optional[str] = None,
    tonic: Optional[Union[int, str]] = None,
    options: Optional[ProcessingOptions] = None,
    config: Optional[AppConfig] = None,
    job_id: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> MaestroResult:
    """Run the whole Maestro engine on *audio_path*.

    Returns a :class:`MaestroResult` object. Use ``result.model_dump()`` for
    a JSON-serializable dict, or ``result.model_dump(mode="json")`` for one
    whose values are already JSON-native types.
    """
    conf = config or get_config()
    opts = options or ProcessingOptions()
    profiler = Profiler()
    profiler.start()

    t0 = _time.perf_counter()
    warnings: list[WarningOut] = []

    # --- tonic -----------------------------------------------------------------
    tonic_midi = _resolve_tonic(tonic, opts)
    if tonic_midi is not None:
        _ = SwaraConverter(tonic_midi)

    # --- audio loading ---------------------------------------------------------
    loader = AudioLoader(conf)
    preprocessor = AudioPreprocessor(conf)
    profiler.mark("config")
    audio = loader.load(audio_path)
    profiler.mark("loading")
    audio = preprocessor.process(audio)
    profiler.mark("preprocessing")

    try:
        op_dir = output_dir or conf.output_dir
        job_label = job_id or _job_label(audio.path or "audio")

        # --- vocal separation ---------------------------------------------------
        skip = bool(opts.vocals_only or opts.skip_separation)
        if skip:
            sep_result = PassthroughSeparator().separate(audio)
            vocals = sep_result.vocals
            vocal_sep = VocalSeparationOut(performed=False, method="passthrough")
            warnings.append(
                WarningOut(code="SEPARATION_SKIPPED", message="Vocal separation skipped by request; using the full mix.", stage="vocal_separation")
            )
        else:
            sep_result, sep_warnings = separate_vocals(
                audio,
                conf,
                output_dir=op_dir if opts.keep_stems else "",
                keep_stems=bool(opts.keep_stems),
            )
            vocals = sep_result.vocals
            for msg in sep_warnings:
                warnings.append(WarningOut(code="VOCAL_SEPARATION_STATUS", message=msg, stage="vocal_separation"))
            vocal_sep = VocalSeparationOut(
                performed=sep_result.separated,
                method=sep_result.method,
                model=sep_result.model,
                device=sep_result.device,
                vocals_path=sep_result.vocals_path,
                instrumental_path=sep_result.instrumental_path,
            )
        profiler.mark("vocal_separation")

        vocals = preprocessor.process(vocals)
        profiler.mark("vocal_preprocessing")

        # --- transcription -------------------------------------------------------
        transcriber = VocalTranscriber(conf)
        result = transcriber.transcribe(vocals, tempo_bpm=opts.tempo_bpm)
        notes = result.notes
        profiler.mark("pitch_detection")
        profiler.mark("note_segmentation")
        if not notes:
            raise MaestroError(
                ErrorCode.NO_NOTES_DETECTED,
                "no musical notes were detected in the vocal input",
            )
        logger.info("Detected %d notes (tempo=%.1f bpm)", len(notes), result.tempo_bpm)

        # persist MIDI artifact
        midi_path = _write_midi(conf, notes, result.tempo_bpm, op_dir, job_label, result)
        profiler.mark("midi_generation")
        logger.info("Wrote MIDI to %s", midi_path)

        # --- swaras ---------------------------------------------------------------
        swarcon = SwaraConverter(tonic_midi)
        swaras = [_swara_out(swarcon, n) for n in notes]
        profiler.mark("swara_conversion")

        # --- lyrics ---------------------------------------------------------------
        lyrics_out = LyricsOut(aligned=False, source="none", confidence=0.0, segments=[])
        lyric_map: dict[int, str] = {}
        lyrics_text = opts.lyrics or lyrics
        lyrics_source = "text"
        if not lyrics_text and opts.transcribe_lyrics:
            try:
                lyrics_text = generate_lyrics(vocals, conf)
                lyrics_source = "whisper"
                if lyrics_text:
                    warnings.append(
                        WarningOut(
                            code="LYRICS_AUTO",
                            message="Lyrics were auto-generated from the vocals.",
                            stage="lyrics",
                        )
                    )
            except MaestroError:
                raise
            except Exception as exc:
                raise MaestroError(
                    ErrorCode.LYRICS_ALIGNMENT_FAILED,
                    f"automatic lyric transcription failed: {exc}",
                ) from exc

        if lyrics_text:
            try:
                units = LyricProcessor().process(lyrics_text)
                aligner = LyricAligner(conf)
                aligned = aligner.align(units, notes)
                segments = _segments(aligned, notes, swarcon)
                lyrics_out = LyricsOut(
                    aligned=True,
                    source=lyrics_source,
                    confidence=_avg([s.confidence for s in segments]),
                    segments=segments,
                )
                for u in aligned:
                    for note_idx in u.notes:
                        if note_idx not in lyric_map:
                            lyric_map[note_idx] = u.word
                if _avg([s.confidence for s in segments]) < 0.5:
                    warnings.append(
                        WarningOut(
                            code="LOW_ALIGNMENT_CONFIDENCE",
                            message="Lyric alignment confidence is low; treat timings as approximate.",
                            stage="lyrics",
                        )
                    )
            except MaestroError:
                raise
            except Exception as exc:
                raise MaestroError(
                    ErrorCode.LYRICS_ALIGNMENT_FAILED,
                    f"lyrics alignment failed: {exc}",
                ) from exc
        profiler.mark("lyrics_alignment")

        # --- notation -------------------------------------------------------------
        notation = NotationGenerator(swarcon).generate(notes, lyric_map)
        profiler.mark("notation")

        # --- assemble result ------------------------------------------------------
        result_obj = MaestroResult(
            metadata=MetadataOut(
                input_format=audio.path.split(".")[-1].lower() if audio.path else None,
                tonic_midi=tonic_midi,
            ).model_dump(),
            audio=AudioInfoOut(
                file_path=audio.path or "upload",
                format=audio.path.split(".")[-1].lower() if audio.path else "upload",
                sample_rate=audio.sample_rate,
                channels=audio.channels_at_load,
                duration=round(audio.duration, 4),
                peak_amplitude=round(audio.peak_amplitude, 4),
            ),
            vocal_separation=vocal_sep,
            tempo=TempoOut(bpm=round(result.tempo_bpm, 2), source=result.tempo_source),
            pitch_analysis=result.pitch_stats,
            midi=result.midi_info,
            swaras=swaras,
            lyrics=lyrics_out,
            notation=notation,
            statistics=ProcessingStatsOut(
                total_seconds=round(_time.perf_counter() - t0, 4),
                stages=profiler.stages,
            ),
            warnings=warnings,
            processing={"note_count": len(notes), "job_id": job_id},
        )
        profiler.mark("assembly")

        # --- validate output ------------------------------------------------------
        validator = OutputValidator()
        validator.validate_result(result_obj)
        validator.validate_midi_file(midi_path)
        logger.info(
            "Pipeline finished: %d notes, %d warnings, %.2fs",
            len(notes),
            len(warnings),
            result_obj.statistics.total_seconds,
        )
        return result_obj

    except MaestroError:
        raise
    except Exception as exc:
        logger.exception("Pipeline crashed unexpectedly")
        raise MaestroError(ErrorCode.INTERNAL_ERROR, f"Unexpected pipeline failure: {exc}", details=type(exc).__name__) from exc


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _job_label(path: str) -> str:
    base = Path(path).stem or "audio"
    return base


def _resolve_tonic(tonic, opts: ProcessingOptions) -> Optional[int]:
    value = tonic if tonic is not None else opts.tonic
    if value is None:
        return None
    if isinstance(value, str):
        parsed = note_name_to_midi(value)
        if parsed is None:
            raise MaestroError(ErrorCode.INVALID_TONIC, f"could not parse tonic note name: {value}")
        return parsed
    tone = int(value)
    if not 0 <= tone <= 127:
        raise MaestroError(ErrorCode.INVALID_TONIC, "tonic must be an integer MIDI note in 0..127")
    return tone


def _write_midi(conf: AppConfig, notes: list[DetectedNote], bpm: float, op_dir: str, label: str, result) -> str:
    from .midi import MidiGenerator

    dest = Path(op_dir) / f"{label}.mid"
    path = MidiGenerator(conf).to_file(notes, bpm, dest)
    result.midi_info.file_path = path
    return path


def _swara_out(swarcon: SwaraConverter, note: DetectedNote) -> SwaraOut:
    pitch = swarcon.convert(note.midi_note, note.frequency)
    return SwaraOut(
        midi_note=round(float(note.midi_note), 4),
        frequency=round(float(note.frequency), 4),
        swara=pitch.swara,
        swara_type=pitch.swara_type,
        octave=pitch.octave,
        cents_from_tonic=round(pitch.cents_from_tonic, 4),
        start=note.start,
        end=note.end,
        duration=note.duration,
        confidence=note.confidence,
    )


def _segments(aligned, notes: list[DetectedNote], swarcon: SwaraConverter) -> list[LyricSegmentOut]:
    segments: list[LyricSegmentOut] = []
    for unit in aligned:
        refs = []
        for idx in unit.notes:
            note = notes[idx]
            pitch = swarcon.convert(note.midi_note, note.frequency)
            refs.append(
                NoteRefOut(
                    swara=pitch.swara,
                    start=note.start,
                    end=note.end,
                    midi_note=round(float(note.midi_note), 4),
                    frequency=round(float(note.frequency), 4),
                )
            )
        segments.append(
            LyricSegmentOut(
                word=unit.word,
                start=unit.start or 0.0,
                end=unit.end or 0.0,
                confidence=unit.confidence,
                alignment_method=unit.alignment_method,
                notes=refs,
            )
        )
    return segments


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0

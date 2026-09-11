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

import numpy as np

from . import __version__
from .audio import AudioLoader, AudioPreprocessor
from .config import AppConfig, ProcessingOptions, get_config
from .errors import ErrorCode, MaestroError
from .hinglish import transliterate_text
from .lyrics import LyricAligner, LyricProcessor
from .lyric_asr import generate_lyrics, TranscriptionResult, WordTimestamp
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
from .swara import SwaraConverter, note_name_to_midi, midi_to_freq
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
    tonic_auto_detected = False
    if tonic_midi is None:
        # Will attempt auto-detection after note detection
        tonic_auto_detected = True
    else:
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
            # Compute diagnostics for passthrough (full mix)
            vocal_rms = float(np.sqrt(np.mean(vocals.mono() ** 2))) if vocals.samples.size > 0 else 0.0
            vocal_peak = float(np.max(np.abs(vocals.mono()))) if vocals.samples.size > 0 else 0.0
            vocal_duration = vocals.duration
            vocal_sep = VocalSeparationOut(
                performed=False,
                method="passthrough",
                vocal_rms=vocal_rms,
                vocal_peak=vocal_peak,
                vocal_duration=vocal_duration,
                instrumental_rms=0.0,
            )
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
                vocal_rms=getattr(sep_result, "vocal_rms", 0.0),
                vocal_peak=getattr(sep_result, "vocal_peak", 0.0),
                vocal_duration=getattr(sep_result, "vocal_duration", 0.0),
                instrumental_rms=getattr(sep_result, "instrumental_rms", 0.0),
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
        if tonic_midi is None:
            # Automatic tonic detection from vocal notes
            from .swara import detect_tonic
            tonic_midi = detect_tonic(notes)
            if tonic_midi is not None:
                logger.info("Auto-detected tonic: MIDI=%d (%.2f Hz)", tonic_midi, midi_to_freq(tonic_midi))
            else:
                # Fallback to C4 if detection fails
                tonic_midi = 60
                warnings.append(
                    WarningOut(code="TONIC_AUTO_FAILED", message="Automatic tonic detection failed; defaulting to C4 (MIDI 60).", stage="swara")
                )
                logger.warning("Tonic auto-detection failed; defaulting to C4 (MIDI 60)")

        swarcon = SwaraConverter(tonic_midi)
        swaras = [_swara_out(swarcon, n) for n in notes]
        profiler.mark("swara_conversion")

        # --- lyrics ---------------------------------------------------------------
        lyrics_out = LyricsOut(aligned=False, source="none", confidence=0.0, segments=[])
        lyric_map: dict[int, list[str]] = {}
        lyrics_text = opts.lyrics or lyrics
        lyrics_source = "text"
        whisper_words: list = []  # Store word timestamps from Whisper
        if not lyrics_text and opts.transcribe_lyrics:
            try:
                transcription = generate_lyrics(vocals, conf)
                lyrics_text = transcription.text
                whisper_words = transcription.words
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

        # Apply transliteration to lyrics text (Hindi/Urdu -> Roman Hinglish)
        # This is a presentation-layer transformation that does NOT affect
        # lyric-note timing, alignment, or notation generation.
        if lyrics_text:
            original_lyrics = lyrics_text
            lyrics_text = transliterate_text(lyrics_text)
            # DEBUG
            with open('debug_pipeline.txt', 'w', encoding='utf-8') as f:
                f.write(f'Original: {original_lyrics}\n')
                f.write(f'Transliterated: {lyrics_text}\n')

        # Also transliterate Whisper word timestamps if available
        if whisper_words:
            for w in whisper_words:
                w.word = transliterate_text(w.word)

        if lyrics_text:
            try:
                processor = LyricProcessor()
                if whisper_words and lyrics_source == "whisper":
                    units = processor.process_with_whisper_timestamps(lyrics_text, whisper_words)
                else:
                    units = processor.process(lyrics_text)
                aligner = LyricAligner(conf)
                aligned = aligner.align(units, notes)
                
                # Diagnostic output
                _print_alignment_diagnostics(aligned, notes, whisper_words)
                
                segments = _segments(aligned, notes, swarcon)
                # Include Whisper word timestamps if available
                word_timestamps = []
                if whisper_words:
                    from .models import WordTimestampOut
                    word_timestamps = [
                        WordTimestampOut(word=w.word, start=w.start, end=w.end, confidence=w.confidence)
                        for w in whisper_words
                    ]
                lyrics_out = LyricsOut(
                    aligned=True,
                    source=lyrics_source,
                    confidence=_avg([s.confidence for s in segments]),
                    segments=segments,
                    word_timestamps=word_timestamps,
                )
                # Build lyric_map using primary ownership (one primary lyric per note)
                for u in aligned:
                    for note_idx in u.notes:
                        if note_idx not in lyric_map:
                            lyric_map[note_idx] = []
                        if u.word not in lyric_map[note_idx]:
                            lyric_map[note_idx].append(u.word)
                
                # DEBUG
                with open('debug_lyric_map.txt', 'w', encoding='utf-8') as f:
                    for k, v in lyric_map.items():
                        f.write(f'note_idx {k}: {v}\n')
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


def _print_alignment_diagnostics(aligned: list, notes: list, whisper_words: list) -> None:
    """Print diagnostic table for lyric-note alignment verification."""
    def safe_print(text: str) -> None:
        """Print text safely, replacing unencodable characters."""
        try:
            print(text)
        except UnicodeEncodeError:
            # Replace unencodable characters
            print(text.encode('ascii', 'replace').decode('ascii'))

    safe_print("\n" + "=" * 80)
    safe_print("LYRIC-NOTE ALIGNMENT DIAGNOSTICS")
    safe_print("=" * 80)
    
    # Word table
    safe_print(f"\n{'WORD':<15} {'START':>8} {'END':>8} {'MATCHED':>8} {'CONF':>6} {'PRIMARY NOTES'}")
    safe_print("-" * 80)
    
    whisper_count = len(whisper_words) if whisper_words else 0
    aligned_count = len(aligned)
    lost_count = 0
    unmatched_count = 0
    matched_words = 0
    
    for unit in aligned:
        word = unit.word
        start = unit.start or 0.0
        end = unit.end or 0.0
        matched = unit.alignment_method != "whisper-unmatched" and unit.alignment_method != "whisper-missing"
        conf = unit.confidence
        note_indices = unit.notes
        
        if note_indices:
            primary_notes = []
            for idx in note_indices:
                if idx < len(notes):
                    note = notes[idx]
                    # Try to get sargam from swarcon if available, else use midi
                    primary_notes.append(f"N{idx}({note.midi_note:.0f})")
            notes_str = ", ".join(primary_notes)
        else:
            notes_str = "none"
            unmatched_count += 1
        
        if not matched:
            lost_count += 1
        else:
            matched_words += 1
            
        safe_print(f"{word:<15} {start:>8.3f} {end:>8.3f} {'YES' if matched else 'NO':>8} {conf:>6.3f} {notes_str}")
    
    # Note table
    safe_print(f"\n{'NOTE':<10} {'START':>8} {'END':>8} {'MIDI':>6} {'PRIMARY LYRIC'}")
    safe_print("-" * 60)
    
    total_notes = len(notes)
    notes_with_lyric = 0
    notes_without_lyric = 0
    
    # Build reverse mapping: note -> primary lyric
    note_primary_lyric: dict[int, str] = {}
    for unit in aligned:
        for note_idx in unit.notes:
            if note_idx not in note_primary_lyric:
                note_primary_lyric[note_idx] = unit.word
    
    for i, note in enumerate(notes):
        primary_lyric = note_primary_lyric.get(i, "none")
        if primary_lyric != "none":
            notes_with_lyric += 1
        else:
            notes_without_lyric += 1
        safe_print(f"N{i:<9} {note.start:>8.3f} {note.end:>8.3f} {note.midi_note:>6.0f} {primary_lyric}")
    
    # Summary
    safe_print("\n" + "=" * 80)
    safe_print("SUMMARY")
    safe_print("=" * 80)
    safe_print(f"Whisper word count:        {whisper_count}")
    safe_print(f"Aligned word count:        {aligned_count}")
    safe_print(f"Lost word count:           {lost_count}")
    safe_print(f"Unmatched word count:      {unmatched_count}")
    safe_print(f"Matched word count:        {matched_words}")
    safe_print(f"Total detected notes:      {total_notes}")
    safe_print(f"Notes with primary lyric:  {notes_with_lyric}")
    safe_print(f"Notes without lyric:       {notes_without_lyric}")
    safe_print("=" * 80)
    safe_print("")

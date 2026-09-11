"""Maestro AI -- simple command-line test runner.

Usage::

    python main.py input/song.mp3 --tonic 60 --lyrics "tu hi mera"

Saves:
    output/maestro.mid
    output/maestro_output.json

The engine itself is independent of this CLI. A future website/API should
call ``maestro.pipeline.process_audio(...)`` directly.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from maestro.config import ProcessingOptions
from maestro.errors import MaestroError
from maestro.pipeline import process_audio


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Maestro AI -- Music Transcription Engine (CLI test runner)",
    )
    parser.add_argument("audio", help="Path to audio file (WAV/MP3/FLAC)")
    parser.add_argument("--tonic", type=str, default="60",
                        help="Sa as MIDI note (e.g. 60) or note name (e.g. C4)")
    parser.add_argument("--lyrics", type=str, default=None,
                        help="Lyric text to align with detected notes")
    parser.add_argument("--output-dir", type=str, default="output",
                        help="Directory for MIDI and JSON output")
    parser.add_argument("--skip-separation", action="store_true",
                        help="Skip vocal separation (use full mix)")
    parser.add_argument("--tempo", type=float, default=None,
                        help="Explicit tempo override (BPM)")
    args = parser.parse_args()

    # Parse tonic (MIDI number or note name)
    tonic_value: int | str
    try:
        tonic_value = int(args.tonic)
    except ValueError:
        tonic_value = args.tonic

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"Error: audio file not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Maestro AI -- Processing: {audio_path.name}")
    print(f"  Tonic: {args.tonic}")
    if args.lyrics:
        print(f"  Lyrics: {args.lyrics}")
    print()

    t0 = time.perf_counter()
    try:
        options = ProcessingOptions(
            tonic=tonic_value,
            lyrics=args.lyrics,
            skip_separation=bool(args.skip_separation),
            tempo_bpm=args.tempo,
        )
        result = process_audio(
            str(audio_path),
            tonic=tonic_value,
            lyrics=args.lyrics,
            options=options,
            output_dir=str(output_dir),
        )
    except MaestroError as exc:
        print(f"\nEngine error [{exc.code.value}]: {exc.message}", file=sys.stderr)
        sys.exit(1)

    elapsed = time.perf_counter() - t0

    # Save JSON
    json_path = output_dir / "maestro_output.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

    midi_path = (result.midi.file_path if result.midi else None) or "N/A"
    note_count = result.processing.get("note_count", 0)
    warnings = result.warnings

    print(f"Done in {elapsed:.2f}s")
    print(f"  Notes detected: {note_count}")
    print(f"  MIDI saved to:  {midi_path}")
    print(f"  JSON saved to:  {json_path}")
    if warnings:
        print(f"  Warnings: {len(warnings)}")
        for w in warnings:
            print(f"    - [{w.code}] {w.message}")
    print()


if __name__ == "__main__":
    main()

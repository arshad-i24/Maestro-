"""Maestro AI -- FastAPI HTTP wrapper.

Exposes the engine to the web frontend:

* ``POST /api/transcribe``  -- upload audio (+ tonic/lyrics/tempo) -> JSON result
* ``GET  /api/midi/{job_id}`` -- download a generated MIDI file

The response of ``/api/transcribe`` is shaped to match what the frontend
renders (duration / tempo / key / timeSignature / instruments / notes).
"""

from __future__ import annotations

import base64
import json
import os
import re
import tempfile
import uuid
import io
from pathlib import Path
from typing import Optional, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from maestro.config import ProcessingOptions, get_config
from maestro.errors import ErrorCode, MaestroError
from maestro.models import MaestroResult
from maestro.pipeline import process_audio

app = FastAPI(title="Maestro AI Engine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_ALLOWED = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}


def _job_label(result: MaestroResult) -> str:
    """Return a stable output label for the given result's raw file.

    The pipeline writes ``<label>.mid`` into the output dir. We compute the
    same label the pipeline used so we can locate the artifact for download.
    """
    base = result.audio.file_path if result.audio and result.audio.file_path else "upload"
    stem = Path(base).stem or "audio"
    return re.sub(r"[^\w.-]", "_", stem)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/transcribe")
async def transcribe(request: Request) -> dict:
    """Accept an audio upload and return a frontend-ready transcription.

    Supports lyrics as either plain text (lyrics) or base64-encoded UTF-8 (lyrics_b64).
    Use lyrics_b64 for non-ASCII scripts (Hindi/Devanagari, Urdu, etc.) to avoid
    multipart form data encoding issues.
    """
    import os
    # Parse multipart form data manually to avoid encoding issues
    form = await request.form()
    
    # DEBUG: Log all form fields
    with open(os.path.join(tempfile.gettempdir(), 'debug_form_fields.txt'), 'w', encoding='utf-8') as f:
        for key, value in form.items():
            if hasattr(value, 'filename'):
                f.write(f'{key}: UploadFile(filename={value.filename}, content_type={value.content_type})\n')
            else:
                f.write(f'{key}: {repr(value)}\n')
    
    audio: UploadFile = form.get("audio")
    if not audio or not audio.filename:
        raise HTTPException(422, "No file was uploaded (missing 'audio' field).")
    
    tonic = form.get("tonic", "60")
    lyrics = form.get("lyrics")
    lyrics_b64 = form.get("lyrics_b64")
    tempo_str = form.get("tempo")
    generate_lyrics_str = form.get("generateLyrics", "false")
    
    suffix = Path(audio.filename).suffix.lower()
    if suffix not in _ALLOWED:
        raise HTTPException(
            400,
            f"Unsupported format '{suffix}'. Supported: {sorted(_ALLOWED)}",
        )

    # Parse tonic (MIDI number or note name, e.g. "60" or "C4").
    tonic_value: Optional[int | str]
    try:
        tonic_value = int(tonic) if tonic else None
    except ValueError:
        tonic_value = tonic or None

    tempo: Optional[float] = float(tempo_str) if tempo_str else None
    generate_lyrics: bool = generate_lyrics_str.lower() == "true"

    # Decode base64 lyrics if provided (for non-ASCII scripts)
    final_lyrics = lyrics
    if lyrics_b64:
        try:
            final_lyrics = base64.b64decode(lyrics_b64).decode('utf-8')
        except Exception as e:
            raise HTTPException(400, f"Invalid base64 lyrics: {e}")

    # DEBUG: Log the received lyrics parameter
    with open(os.path.join(tempfile.gettempdir(), 'debug_lyrics_param.txt'), 'w', encoding='utf-8') as f:
        f.write(f'lyrics param: {repr(final_lyrics)}\n')
        f.write(f'lyrics bytes: {final_lyrics.encode("utf-8") if final_lyrics else None}\n')
        f.write(f'generateLyrics: {generate_lyrics}\n')

    options = ProcessingOptions(
        tonic=tonic_value,
        lyrics=final_lyrics,
        skip_separation=False,
        tempo_bpm=tempo,
        transcribe_lyrics=generate_lyrics,
    )

    content = await audio.read()
    if not content:
        raise HTTPException(400, "Uploaded audio is empty.")

    job_id = uuid.uuid4().hex[:12]
    try:
        result = process_audio(
            io.BytesIO(content),
            tonic=tonic_value,
            lyrics=final_lyrics,
            options=options,
            config=get_config(),
            job_id=job_id,
        )
    except MaestroError as exc:
        raise HTTPException(status_code=_status_for(exc.code), detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected engine failure: {exc}") from exc

    frontend_result = _to_frontend(result)
    
    # DEBUG: Log the frontend result to file (absolute path)
    import json
    import os
    debug_json = json.dumps(frontend_result, ensure_ascii=False)
    debug_path = os.path.join(os.path.dirname(__file__), 'debug_frontend.txt')
    with open(debug_path, 'w', encoding='utf-8') as f:
        f.write(debug_json[:1000])
    
    response_dict = {
        "jobId": job_id,
        "midiUrl": f"/api/midi/{job_id}",
        "result": frontend_result,
    }
    return JSONResponse(content=response_dict, media_type="application/json; charset=utf-8")


@app.get("/api/midi/{job_id}")
def download_midi(job_id: str) -> FileResponse:
    """Download the MIDI file for a completed job."""
    conf = get_config()
    out_dir = Path(conf.output_dir)
    matches = list(out_dir.glob(f"{job_id}*.mid"))
    if not matches:
        raise HTTPException(404, f"No MIDI file found for job '{job_id}'.")
    return FileResponse(str(matches[0]), media_type="audio/midi", filename=f"{job_id}.mid")


def _status_for(code: ErrorCode) -> int:
    if code in (ErrorCode.INVALID_AUDIO, ErrorCode.UNSUPPORTED_FORMAT):
        return 400
    if code in (ErrorCode.AUDIO_TOO_SHORT, ErrorCode.AUDIO_TOO_LONG, ErrorCode.AUDIO_EMPTY):
        return 422
    if code == ErrorCode.NO_NOTES_DETECTED:
        return 422
    if code == ErrorCode.INVALID_TONIC:
        return 400
    return 500


def _to_frontend(result: MaestroResult) -> dict:
    """Map a MaestroResult into the shape the frontend renders.

    The engine transcribes vocals into Hindustani swaras + MIDI notes; it does
    not detect western key, time signature, or polyphonic instrument stems. We
    provide sensible defaults for those fields so the existing UI renders.
    """
    import os
    import traceback
    duration_s = float(result.audio.duration) if result.audio else 0.0
    bpm = float(result.tempo.bpm) if result.tempo and result.tempo.bpm else None

    key_text, _ = _infer_key(result)
    time_sig = _time_signature(result)

    notes = []
    for entry in result.notation:
        mm, ss = _fmt_time(entry.start)
        # DEBUG - write to a known absolute path
        debug_path = r'C:\Users\arsha\OneDrive\Desktop\debug_to_frontend.txt'
        try:
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(f'CWD: {os.getcwd()}\n')
                f.write(f'FILE: {__file__}\n')
                f.write(f'entry.lyric: {repr(entry.lyric)}\n')
                f.write(f'entry.lyric bytes: {entry.lyric.encode("utf-8") if entry.lyric else None}\n')
                f.write(f'entry.lyric type: {type(entry.lyric)}\n')
        except Exception as e:
            with open(r'C:\Users\arsha\OneDrive\Desktop\debug_error.txt', 'w', encoding='utf-8') as f:
                f.write(f'Error writing debug: {e}\n{traceback.format_exc()}')
        # Split lyrics by comma if multiple, but keep as array for frontend
        lyric_parts = []
        if entry.lyric:
            lyric_parts = [part.strip() for part in entry.lyric.split(",") if part.strip()]
        try:
            with open(r'C:\Users\arsha\OneDrive\Desktop\debug_to_frontend.txt', 'a', encoding='utf-8') as f:
                f.write(f'lyric_parts: {lyric_parts}\n')
        except Exception as e:
            with open(r'C:\Users\arsha\OneDrive\Desktop\debug_error.txt', 'w', encoding='utf-8') as f:
                f.write(f'Error writing lyric_parts: {e}\n{traceback.format_exc()}')
        notes.append(
            {
                "time": f"{mm}:{ss}",
                "start": round(entry.start, 3),
                "end": round(entry.end, 3),
                "duration": round(entry.duration, 3),
                "instrument": "Vocal",
                "note": entry.symbol or entry.swara,
                "duration_str": f"{entry.duration:.2f}s",
                "lyric": lyric_parts,  # Array of lyric parts for this note
            }
        )

    # Include lyrics segments for phrase-based rendering
    lyrics_segments = []
    if result.lyrics and result.lyrics.segments:
        lyrics_segments = [
            {
                "word": seg.word,
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "confidence": seg.confidence,
            }
            for seg in result.lyrics.segments
        ]

    return {
        "duration": _fmt_duration(duration_s),
        "tempo": int(round(bpm)) if bpm else 0,
        "key": key_text,
        "timeSignature": time_sig,
        "instruments": _instruments(result),
        "notes": notes,
        "lyricsSource": result.lyrics and result.lyrics.source or "none",
        "lyrics": {
            "segments": lyrics_segments,
            "aligned": result.lyrics.aligned if result.lyrics else False,
        } if result.lyrics else None,
    }


def _infer_key(result: MaestroResult) -> tuple[str, Optional[str]]:
    """Derive a Western key label from the tonic (Sa) if available."""
    tonic = result.metadata.get("tonic_midi") if result.metadata else None
    if tonic is None:
        return "Unknown", None
    try:
        names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        pc = int(tonic) % 12
        return f"{names[pc]} Major", names[pc]
    except Exception:
        return "Unknown", None


def _time_signature(result: MaestroResult) -> str:
    bpm = float(result.tempo.bpm) if result.tempo and result.tempo.bpm else None
    if bpm is None:
        return "4/4"
    # No beat/subdivision detection is implemented; default to common 4/4.
    return "4/4"


def _instruments(result: MaestroResult) -> list[str]:
    if result.vocal_separation and result.vocal_separation.performed:
        return ["Vocal"]
    return ["Vocal (full mix)"]


def _fmt_duration(seconds: float) -> str:
    total = int(round(seconds))
    m, s = divmod(total, 60)
    return f"{m:02d}:{s:02d}"


def _fmt_time(seconds: float) -> tuple[str, str]:
    total = int(seconds)
    m, s = divmod(total, 60)
    return f"{m:02d}", f"{s:02d}"


# ---------------------------------------------------------------------------
# Static frontend serving (single-server mode)
#
# If the frontend has been built (frontend/dist exists), FastAPI serves it at
# the root "/" so the whole site runs from one process and one port. The API
# routes above always take precedence (they are registered first).
# ---------------------------------------------------------------------------

_DIST = Path(__file__).resolve().parent / "frontend" / "dist"
_INDEX = _DIST / "index.html"


@app.get("/", include_in_schema=False)
def root():
    if _INDEX.exists():
        return FileResponse(_INDEX)
    return {
        "message": "Maestro backend is running. Build the frontend (cd frontend && npm install && npm run build) to serve the website from this server, or call /api/transcribe directly.",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    """Serve built frontend assets; SPA fallback to index.html."""
    if not _INDEX.exists():
        from fastapi.responses import JSONResponse
        return JSONResponse(
            {"message": "Frontend is not built yet. See / for instructions."},
            status_code=404,
        )
    candidate = (_DIST / full_path).resolve()
    # Prevent path traversal outside dist.
    if not str(candidate).startswith(str(_DIST.resolve())):
        return FileResponse(_INDEX)
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(_INDEX)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
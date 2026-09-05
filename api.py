"""Maestro AI -- FastAPI HTTP wrapper.

Exposes the engine to the web frontend:

* ``POST /api/transcribe``  -- upload audio (+ tonic/lyrics/tempo) -> JSON result
* ``GET  /api/midi/{job_id}`` -- download a generated MIDI file

The response of ``/api/transcribe`` is shaped to match what the frontend
renders (duration / tempo / key / timeSignature / instruments / notes).
"""

from __future__ import annotations

import re
import uuid
import io
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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
async def transcribe(
    audio: UploadFile = File(...),
    tonic: Optional[str] = Form(default="60"),
    lyrics: Optional[str] = Form(default=None),
    tempo: Optional[float] = Form(default=None),
    generateLyrics: Optional[bool] = Form(default=False),
) -> dict:
    """Accept an audio upload and return a frontend-ready transcription."""
    if not audio.filename:
        raise HTTPException(400, "No file was uploaded (missing 'audio' field).")

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

    options = ProcessingOptions(
        tonic=tonic_value,
        lyrics=lyrics,
        skip_separation=False,
        tempo_bpm=tempo,
        transcribe_lyrics=bool(generateLyrics),
    )

    content = await audio.read()
    if not content:
        raise HTTPException(400, "Uploaded audio is empty.")

    job_id = uuid.uuid4().hex[:12]
    try:
        result = process_audio(
            io.BytesIO(content),
            tonic=tonic_value,
            lyrics=lyrics,
            options=options,
            config=get_config(),
            job_id=job_id,
        )
    except MaestroError as exc:
        raise HTTPException(status_code=_status_for(exc.code), detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected engine failure: {exc}") from exc

    return {
        "jobId": job_id,
        "midiUrl": f"/api/midi/{job_id}",
        "result": _to_frontend(result),
    }


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
    duration_s = float(result.audio.duration) if result.audio else 0.0
    bpm = float(result.tempo.bpm) if result.tempo and result.tempo.bpm else None

    key_text, _ = _infer_key(result)
    time_sig = _time_signature(result)

    notes = []
    for entry in result.notation:
        mm, ss = _fmt_time(entry.start)
        notes.append(
            {
                "time": f"{mm}:{ss}",
                "instrument": "Vocal",
                "note": entry.symbol or entry.swara,
                "duration": f"{entry.duration:.2f}s",
                "lyric": entry.lyric or None,
            }
        )

    return {
        "duration": _fmt_duration(duration_s),
        "tempo": int(round(bpm)) if bpm else 0,
        "key": key_text,
        "timeSignature": time_sig,
        "instruments": _instruments(result),
        "notes": notes,
        "lyricsSource": result.lyrics and result.lyrics.source or "none",
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

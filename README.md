# Maestro AI Engine

**Maestro AI Engine** is a Python-based AI/music-processing engine with a React
web frontend. It converts music/vocal audio into structured musical
information and serves the results through a FastAPI backend.

The **core engine** is a clean, reusable AI library that accepts audio and
parameters and returns structured results. The **`api.py` FastAPI app** exposes
it over HTTP and serves the React UI (under `frontend/`).

```
Audio → Vocal Separation → Pitch Detection → Note Detection → MIDI →
Hindustani Swara Conversion → Lyrics Alignment → Musical Notation → JSON Result
```

---

## Project structure

```
maestro_engine/
│
├── maestro/
│   ├── audio.py      # load (WAV/MP3/FLAC) + preprocessing
│   ├── vocal.py      # vocal separation (Demucs) + passthrough fallback
│   ├── pitch.py      # pitch detection (pYIN/STFT) + note segmentation
│   ├── midi.py       # MIDI generation (mido)
│   ├── swara.py      # MIDI → Hindustani swara (configurable tonic)
│   ├── lyrics.py     # lyric → note alignment (simple, word-based)
│   ├── notation.py   # Hindustani musical notation
│   ├── pipeline.py   # process_audio() orchestrator
│   ├── models.py     # dataclasses + output schema
│   ├── config.py     # configuration + per-request options
│   ├── errors.py     # structured errors
│   ├── validation.py # output sanity checks
│   └── log.py        # JSON logging
│
├── frontend/         # React (Vite) web app — UI + /api calls
├── api.py            # FastAPI wrapper: API + serves the built frontend
├── tests/
│   └── test_*.py     # basic tests (synthetic audio)
│
├── input/            # place audio files here
├── output/           # MIDI + JSON artifacts written here
├── main.py           # simple CLI test runner
├── requirements.txt
└── README.md
```

---

## Installation

Requires **Python 3.10+**.

```bash
cd maestro_engine
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # Linux / macOS

pip install -r requirements.txt
```

**Optional — real vocal separation (Demucs):**

```bash
pip install -r requirements-vocal.txt   # torch + demucs (large download)
```

Without it the engine still runs in *passthrough* mode: the full mix is used
as the vocal stem and a warning is included in the result.

## Dependencies

| Package            | Purpose                            |
|--------------------|------------------------------------|
| `numpy`, `scipy`   | numerical DSP                      |
| `soundfile`, `librosa` | decode, resample, pYIN, tempo  |
| `mido`             | Standard MIDI File write/validate  |
| `pydantic`         | output schema                      |
| `torch`, `demucs`  | vocal separation (optional)        |
| `faster-whisper`   | auto-generate lyrics from vocals   |

## How to run

Simple CLI test runner:

```bash
python main.py input/song.mp3 --tonic 60 --lyrics "tu hi mera"
```

This runs the engine and saves:

```
output/maestro.mid
output/maestro_output.json
```

Both are produced regardless of whether lyrics are provided.

### Engine usage (programmatic)

This is what a future website/API will call. All processing logic is kept
separate from `main.py`.

```python
from maestro import process_audio

result = process_audio(
    "input/song.mp3",
    tonic=60,
    lyrics="tu hi mera",
    output_dir="output",
)
# result is a MaestroResult object
json_data = result.model_dump(mode="json")
midi_path = result.midi.file_path   # → output/maestro.mid
```

The engine does not depend on command-line input internally.

## Web app (FastAPI + React frontend)

This repository also contains the React frontend (under `frontend/`) and a
FastAPI wrapper (`api.py`) that serves both the API and the website from a
**single server** on one port.

### One-time frontend setup

```bash
cd frontend
npm install          # installs React/Vite deps (node_modules is git-ignored)
npm run build        # builds static site into frontend/dist
cd ..
```

### Run the full website (single server)

```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/` — FastAPI serves the built React app and the
API together. Interactive API docs at `http://127.0.0.1:8000/docs`.

Endpoints:
- `POST /api/transcribe` — multipart upload (`audio` field) + optional
  `tonic`, `lyrics`, `tempo`, `generateLyrics`; returns a frontend-ready JSON
  transcription and a `midiUrl`. Send `generateLyrics=true` to auto-transcribe
  the vocals into lyrics with Whisper (instead of, or on top of, pasted text).
- `GET /api/midi/{job_id}` — download the generated MIDI file.
- `GET /api/health` — liveness check.

### Development mode (two processes)

Run the backend and let Vite proxy `/api` → `:8000`:

```bash
# terminal 1 — backend
python -m uvicorn api:app --port 8000

# terminal 2 — frontend (live-reload UI)
cd frontend && npm run dev     # opens / proxies to :8000
```

## How to run tests

```bash
pytest
```

All tests use synthetic (generated sine-wave) audio, so nothing needs
downloading. Coverage includes audio loading, preprocessing, vocal separation
interface, pitch detection, note segmentation, MIDI generation, MIDI→swara
conversion, lyrics alignment, notation generation, JSON generation, and the
complete pipeline.

## JSON output

`process_audio` returns a `MaestroResult` whose `model_dump(mode="json")` is:

```json
{
  "metadata": {},
  "audio": {},
  "vocal_separation": {},
  "tempo": {},
  "pitch_analysis": {},
  "midi": {},
  "swaras": [],
  "lyrics": [],
  "notation": [],
  "statistics": {},
  "warnings": [],
  "processing": {}
}
```

- `midi.notes` — `{pitch, start, end, duration}`
- `swaras` — `{midi_note, frequency, swara, swara_type, octave, start, end, duration, confidence}`
- `notation` — `{swara, octave, start, end, duration, lyric, confidence, symbol}`
- `lyrics.segments` — `{word, start, end, confidence, notes}`

Every numeric field is guaranteed finite (no NaN/Inf), confidences are in
`[0,1]`, note times are ordered, durations > 0, pitches in `0..127`.

### Hindustani swara mapping

With a configurable tonic (`Sa`), relative semitone distance maps to:

```text
0  = Sa        4  = Ga        8  = komal Dha
1  = komal Re  5  = Ma        9  = Dha
2  = Re        6  = tivra Ma  10 = komal Ni
3  = komal Ga  7  = Pa        11 = Ni
```

Octaves: `.Sa` (mandra / lower), `Sa` (madhya / middle), `'Sa` (taar / upper).

## Configuration

`AppConfig` in `maestro/config.py` holds every tuneable (sample rate, pitch
ranges, note segmentation thresholds, MIDI settings, vocal separation model,
paths). `ProcessingOptions` holds per-request overrides. Defaults work for
typical input; the tonic is NOT hard-coded — pass it via `process_audio(..., tonic=...)`.

## Error handling

Structured, machine-readable errors via `MaestroError` (`.code`, `.message`,
`.details`). Invalid/empty/unsupported/corrupt audio, no-notes-detected, and
internal failures all raise typed errors rather than crashing silently.

## Design notes

- Modular and swappable stages (pitch detector, separator, notation) behind
  small interfaces.
- Uses real libraries for actual audio analysis — no faked results.
- No hard-coded file paths or hard-coded tonic.
- No database, auth, or payments.

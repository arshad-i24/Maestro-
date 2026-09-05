"""API tests for the FastAPI wrapper (api.py)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api as api_module
from api import app

from maestro.config import AppConfig


@pytest.fixture()
def test_config(tmp_path):
    """A separation-free config pointed at a temp output dir for fast tests."""
    conf = AppConfig(
        output_dir=str(tmp_path / "output"),
        input_dir=str(tmp_path / "input"),
        vocal_separation_model="none",
        device="cpu",
        keep_stems=False,
        sample_rate=22050,
    )
    return conf


@pytest.fixture()
def client(monkeypatch, test_config):
    # Point the API at the fast test config (no Demucs), isolated output dir.
    monkeypatch.setattr(api_module, "get_config", lambda: test_config)
    return TestClient(app)


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_transcribe_returns_frontend_shape(client, sine_wav):
    with open(sine_wav, "rb") as fh:
        res = client.post(
            "/api/transcribe",
            files={"audio": ("sine.wav", fh, "audio/wav")},
            data={"tonic": "60"},
        )
    assert res.status_code == 200
    body = res.json()
    assert "jobId" in body
    assert "midiUrl" in body
    result = body["result"]
    assert "duration" in result
    assert "tempo" in result
    assert "key" in result
    assert "timeSignature" in result
    assert isinstance(result["instruments"], list)
    assert isinstance(result["notes"], list)


def test_transcribe_rejects_missing_file(client):
    res = client.post("/api/transcribe")
    assert res.status_code == 422  # FastAPI validation (missing Form/File)


def test_transcribe_rejects_unsupported_format(client):
    res = client.post(
        "/api/transcribe",
        files={"audio": ("song.exe", b"MZ...", "application/octet-stream")},
    )
    assert res.status_code == 400


def test_download_midi_missing_returns_404(client):
    res = client.get(f"/api/midi/{'0' * 12}")
    assert res.status_code == 404


def test_download_midi_roundtrip(client, sine_wav):
    with open(sine_wav, "rb") as fh:
        res = client.post(
            "/api/transcribe",
            files={"audio": ("sine.wav", fh, "audio/wav")},
            data={"tonic": "60"},
        )
    assert res.status_code == 200
    job_id = res.json()["jobId"]
    mid = client.get(f"/api/midi/{job_id}")
    assert mid.status_code == 200
    assert mid.headers["content-type"].startswith("audio/")
    assert len(mid.content) > 0

"""Maestro AI — music transcription engine (backend only)."""

from __future__ import annotations

__version__ = "0.1.0"

from .pipeline import process_audio  # noqa: E402,F401

__all__ = ["process_audio", "__version__"]

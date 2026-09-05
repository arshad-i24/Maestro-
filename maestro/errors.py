"""Structured, typed errors used across the Maestro engine.

Every failure that is surfaced to callers / the API is wrapped in a
:class:`MaestroError` carrying a stable error code, a human-readable message
and optional details. Components never swallow failures silently.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional


class ErrorCode(str, Enum):
    """Stable machine-readable error codes exposed by the API."""

    INVALID_AUDIO = "INVALID_AUDIO"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    AUDIO_TOO_SHORT = "AUDIO_TOO_SHORT"
    AUDIO_TOO_LONG = "AUDIO_TOO_LONG"
    AUDIO_EMPTY = "AUDIO_EMPTY"
    AUDIO_LOAD_FAILED = "AUDIO_LOAD_FAILED"
    VOCAL_SEPARATION_FAILED = "VOCAL_SEPARATION_FAILED"
    PITCH_DETECTION_FAILED = "PITCH_DETECTION_FAILED"
    NOTE_SEGMENTATION_FAILED = "NOTE_SEGMENTATION_FAILED"
    MIDI_GENERATION_FAILED = "MIDI_GENERATION_FAILED"
    INVALID_TONIC = "INVALID_TONIC"
    LYRICS_ALIGNMENT_FAILED = "LYRICS_ALIGNMENT_FAILED"
    NOTATION_GENERATION_FAILED = "NOTATION_GENERATION_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    NO_NOTES_DETECTED = "NO_NOTES_DETECTED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class MaestroError(Exception):
    """Base error for all Maestro failures.

    Attributes:
        code: stable :class:`ErrorCode` value.
        message: user-facing description.
        details: optional free-form detail (dict or str).
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_dict(self) -> dict:
        payload: dict[str, Any] = {"code": self.code.value, "message": self.message}
        if self.details is not None:
            payload["details"] = self.details
        return payload

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"MaestroError(code={self.code.value}, message={self.message!r})"


def wrap_exception(exc: Exception, code: ErrorCode, message: str) -> MaestroError:
    """Convert a generic exception into a MaestroError, preserving the cause."""
    return MaestroError(code, f"{message}: {exc}", details=type(exc).__name__)
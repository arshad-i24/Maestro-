"""Structured logging configuration.

Logs are JSON-lines to stderr so they can be piped into any log pipeline,
while still being human readable in development. Levels: engine runtime logs
at INFO; each Maestro module uses ``maestro.<subsystem>`` loggers.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    # avoid duplicate handlers on repeated calls (e.g. tests + import)
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    # quiet noisy third-party loggers
    logging.getLogger("demucs").setLevel(logging.WARNING)
    logging.getLogger("librosa").setLevel(logging.WARNING)
    logging.getLogger("maestro").debug("logging initialized (level=%s)", logging.getLevelName(level))
"""Structured logging configuration.

Configures Python's standard library logging with a minimal JSON formatter and
an env-driven log level.

This is deliberately infrastructure-only: no run_id correlation, no per-agent
cost tracking, and no persistence to the Database Layer. The full
observability requirements from DEVELOPER_HANDBOOK.md section 8 and
AGENT_SPECIFICATIONS.md section 5 (reasoning traces, cost ledgers tied to
run_id) belong to the Core Infrastructure milestone (tracing.py,
cost_tracking.py in this same package), not Day 0 repository foundation.
"""

from __future__ import annotations

import json
import logging
import logging.config
from datetime import UTC, datetime
from typing import Any


class _JsonFormatter(logging.Formatter):
    """Minimal structured formatter -- one JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging for the whole application.

    Call once, at process startup (a future API entrypoint, worker
    entrypoint, or a script's `__main__` block). Safe to call more than
    once -- `dictConfig` replaces the prior configuration rather than
    stacking handlers.
    """
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": _JsonFormatter}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                }
            },
            "root": {"handlers": ["console"], "level": level.upper()},
        }
    )

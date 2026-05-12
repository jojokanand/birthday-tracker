"""Structured JSON logging configuration.

We use :mod:`structlog` because it gives us per-call key/value context (request
IDs, user IDs, etc.) for free and renders cleanly as JSON for Cloud Logging.
The stdlib ``logging`` module is configured to forward through structlog so
third-party libraries (FastAPI, Uvicorn, google-cloud-firestore) participate
in the same pipeline.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor


def _add_severity(_logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add a Cloud Logging-friendly ``severity`` field.

    structlog logs a ``level`` key by default; Google Cloud Logging keys off
    ``severity``. We mirror the level into both so logs render correctly in
    GCP without losing local readability.

    Args:
        _logger: structlog logger (unused — required by the processor signature).
        method_name: The level method invoked (``"info"``, ``"warning"``, ...).
        event_dict: The mutable event dictionary so far.

    Returns:
        The same ``event_dict`` with ``severity`` set to the uppercase level.
    """
    event_dict["severity"] = method_name.upper()
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    """Wire structlog and the stdlib root logger to emit JSON to stdout.

    Idempotent: calling twice replaces the configuration rather than stacking
    handlers, so test fixtures can reconfigure freely.

    Args:
        level: Minimum log level (``"DEBUG"``, ``"INFO"``, ``"WARNING"``, ...).
            Comes from :class:`birthday_tracker.core.config.Settings.log_level`.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Replace any existing handlers so re-configuration in tests is clean.
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    root.addHandler(handler)
    root.setLevel(log_level)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        _add_severity,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Return a structlog logger bound to ``name``.

    Args:
        name: Logger name, typically ``__name__`` from the calling module.
            ``None`` returns the root structlog logger.

    Returns:
        A bound logger ready for ``.info(...)`` / ``.error(...)`` calls. Typed
        as :data:`Any` because structlog's runtime wrapper class depends on
        configuration; the public methods (``info``, ``warning``, ``error``,
        ``exception``, ``debug``) are stable regardless.
    """
    return structlog.get_logger(name)

"""Unit tests for the structured logging configuration."""

from __future__ import annotations

import io
import json
import logging

import pytest

from birthday_tracker.core.logging import configure_logging, get_logger


@pytest.mark.unit
def test_configure_logging_emits_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Logger output must be valid JSON with severity + timestamp + event keys."""
    buffer = io.StringIO()
    monkeypatch.setattr("sys.stdout", buffer)

    configure_logging(level="DEBUG")
    log = get_logger("test")
    log.info("hello", foo="bar")

    line = buffer.getvalue().strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["event"] == "hello"
    assert payload["foo"] == "bar"
    assert payload["severity"] == "INFO"
    assert "timestamp" in payload


@pytest.mark.unit
def test_configure_logging_respects_level(monkeypatch: pytest.MonkeyPatch) -> None:
    buffer = io.StringIO()
    monkeypatch.setattr("sys.stdout", buffer)

    configure_logging(level="WARNING")
    log = get_logger("test")
    log.info("should-not-appear")
    log.warning("should-appear")

    output = buffer.getvalue()
    assert "should-not-appear" not in output
    assert "should-appear" in output


@pytest.mark.unit
def test_configure_logging_is_idempotent() -> None:
    """Re-configuring should not stack stdlib handlers."""
    configure_logging(level="INFO")
    initial_handler_count = len(logging.getLogger().handlers)
    configure_logging(level="INFO")
    assert len(logging.getLogger().handlers) == initial_handler_count

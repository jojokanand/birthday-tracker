"""Unit tests for the in-memory rate limiter."""

from __future__ import annotations

import pytest

from birthday_tracker.core.rate_limit import RateLimiter, RateLimitExceeded


class _FakeClock:
    """Manually-advanced clock for deterministic limiter tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.mark.unit
def test_constructor_rejects_non_positive_max() -> None:
    with pytest.raises(ValueError, match="max_per_window must be positive"):
        RateLimiter(max_per_window=0)


@pytest.mark.unit
def test_below_threshold_is_allowed() -> None:
    clock = _FakeClock()
    limiter = RateLimiter(max_per_window=3, window_seconds=60.0, clock=clock)
    for _ in range(3):
        limiter.hit("k")  # no raise


@pytest.mark.unit
def test_above_threshold_raises() -> None:
    clock = _FakeClock()
    limiter = RateLimiter(max_per_window=2, window_seconds=60.0, clock=clock)
    limiter.hit("k")
    limiter.hit("k")
    with pytest.raises(RateLimitExceeded):
        limiter.hit("k")


@pytest.mark.unit
def test_window_slides_with_time() -> None:
    clock = _FakeClock()
    limiter = RateLimiter(max_per_window=2, window_seconds=10.0, clock=clock)
    limiter.hit("k")
    limiter.hit("k")
    clock.advance(11.0)  # window has fully passed
    limiter.hit("k")  # should succeed


@pytest.mark.unit
def test_keys_are_isolated() -> None:
    clock = _FakeClock()
    limiter = RateLimiter(max_per_window=1, window_seconds=60.0, clock=clock)
    limiter.hit("a")
    limiter.hit("b")  # different bucket, fine

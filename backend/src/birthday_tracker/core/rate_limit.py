"""In-memory sliding-window rate limiter keyed by an arbitrary string.

Sized for personal-use traffic on a single Cloud Run instance. If we ever
horizontally scale, swap this for a Redis- or Firestore-backed limiter — the
:class:`RateLimiter` interface stays the same.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable


class RateLimitExceeded(Exception):
    """Raised when a key has used up its allowance for the current window."""


class RateLimiter:
    """Bounded-allowance sliding window per ``key``.

    Each ``key`` (typically a form token) keeps a deque of recent request
    timestamps. A new request is rejected when the deque already holds
    ``max_per_window`` entries within the last ``window_seconds`` seconds.

    Attributes:
        max_per_window: Number of requests allowed inside one window.
        window_seconds: Window length in seconds.
    """

    def __init__(
        self,
        max_per_window: int,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Build the limiter.

        Args:
            max_per_window: Max requests per ``window_seconds`` per key.
                Must be positive.
            window_seconds: Window duration. Default 60s.
            clock: Monotonic clock function (overridable in tests).

        Raises:
            ValueError: If ``max_per_window`` is non-positive.
        """
        if max_per_window <= 0:
            raise ValueError("max_per_window must be positive")
        self.max_per_window = max_per_window
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> None:
        """Record one request against ``key``, raising if over the limit.

        Args:
            key: The bucket identifier (e.g. raw form token).

        Raises:
            RateLimitExceeded: If ``key`` has already used its allowance for
                the current window.
        """
        now = self._clock()
        cutoff = now - self.window_seconds
        bucket = self._hits.setdefault(key, deque())

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= self.max_per_window:
            raise RateLimitExceeded(
                f"rate limit exceeded: {self.max_per_window} req/{self.window_seconds:g}s"
            )

        bucket.append(now)

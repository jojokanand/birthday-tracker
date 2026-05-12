"""Readiness checks for downstream dependencies.

Kept separate from the route handlers so the same probes can be reused by
background workers (digest sender, etc.) and by tests.
"""

from __future__ import annotations

from dataclasses import dataclass

from birthday_tracker.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ReadinessResult:
    """Outcome of a readiness probe.

    Attributes:
        ok: ``True`` when the dependency is reachable.
        detail: Optional explanation, populated on failure for ops triage.
    """

    ok: bool
    detail: str | None = None


async def check_firestore(project_id: str, emulator_host: str | None = None) -> ReadinessResult:
    """Verify the Firestore client can reach the backend.

    The check imports :mod:`google.cloud.firestore` lazily so the module can
    be imported in environments without GCP libraries installed (CI for
    components that don't need Firestore). It performs the cheapest possible
    operation — listing the first collection — and treats any exception as
    a failure.

    Args:
        project_id: GCP project ID. May be empty when ``emulator_host`` is
            set, in which case the emulator accepts a default project.
        emulator_host: ``host:port`` of a local Firestore emulator. When
            provided, the SDK reads ``FIRESTORE_EMULATOR_HOST`` from the env
            (set by the caller) and skips real auth.

    Returns:
        :class:`ReadinessResult` with ``ok=True`` on success or a populated
        ``detail`` on failure.
    """
    try:
        from google.cloud import firestore  # noqa: PLC0415  (lazy import for testability)

        client = firestore.AsyncClient(project=project_id or "demo-project")
        # Touch the API: iterate `collections()` once. Cheapest round-trip
        # the SDK exposes that proves credentials + reachability.
        async for _ in client.collections():
            break
        return ReadinessResult(ok=True)
    except Exception as exc:  # noqa: BLE001  (we intentionally swallow everything)
        logger.warning(
            "firestore_readiness_failed",
            project=project_id,
            emulator=emulator_host,
            error=str(exc),
        )
        return ReadinessResult(ok=False, detail=str(exc))

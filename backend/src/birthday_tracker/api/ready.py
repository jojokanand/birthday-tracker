"""Readiness probe.

Distinct from :mod:`birthday_tracker.api.health`: ``/health`` answers "is the
process up?" while ``/ready`` answers "can the process serve traffic?". The
latter requires Firestore to be reachable; if it is not we return 503 so
Cloud Run / load balancers stop sending traffic to this instance.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from birthday_tracker.core.config import Settings, get_settings
from birthday_tracker.core.health import check_firestore

router = APIRouter(tags=["health"])


class ReadinessResponse(BaseModel):
    """Payload returned by :func:`get_ready`.

    Attributes:
        status: ``"ready"`` on success, ``"not_ready"`` on failure.
        firestore: ``"ok"`` or a short failure description.
    """

    status: str
    firestore: str


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe (pings Firestore)",
    responses={503: {"description": "Firestore unreachable"}},
)
async def get_ready(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> ReadinessResponse:
    """Return readiness state, including a live Firestore ping.

    Args:
        response: Injected so we can flip the status code to 503 when the
            downstream check fails without raising.
        settings: Process settings (project ID, optional emulator host).

    Returns:
        :class:`ReadinessResponse` describing the outcome. The HTTP status is
        200 when ready, 503 otherwise.
    """
    result = await check_firestore(
        project_id=settings.gcp_project_id,
        emulator_host=settings.firestore_emulator_host or None,
    )
    if not result.ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="not_ready", firestore=result.detail or "unreachable")
    return ReadinessResponse(status="ready", firestore="ok")

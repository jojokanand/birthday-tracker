"""Health-check router.

Used by Cloud Run, load balancers, and the CI smoke test to verify the API is
running. Returns a tiny payload — keep it cheap.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from birthday_tracker import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Payload returned by :func:`get_health`.

    Attributes:
        status: Always ``"ok"`` when the process can serve a response.
        version: Package version string for the running build.
    """

    status: str
    version: str


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def get_health() -> HealthResponse:
    """Return a static liveness payload.

    Returns:
        A :class:`HealthResponse` indicating the service is up. Does not check
        downstream dependencies on purpose — readiness checks belong in a
        separate endpoint that we will add when wiring Firestore.
    """
    return HealthResponse(status="ok", version=__version__)

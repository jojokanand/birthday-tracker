"""RFC 7807 problem+json error model and FastAPI exception handlers.

All error responses from the API conform to
https://datatracker.ietf.org/doc/html/rfc7807, which defines a small JSON
object with ``type``, ``title``, ``status``, ``detail``, and ``instance``
members. Returning a uniform shape makes the dashboard's error handling
trivial and gives operators a stable schema to alert on.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from birthday_tracker.core.logging import get_logger

logger = get_logger(__name__)

PROBLEM_JSON = "application/problem+json"


class ProblemDetail(BaseModel):
    """RFC 7807 problem+json payload.

    Attributes:
        type: URI identifying the problem class. ``"about:blank"`` is the
            sentinel meaning "no further information beyond the HTTP status".
        title: Short, human-readable summary.
        status: HTTP status code, mirrored into the body for clients that
            cannot easily read response headers.
        detail: Optional longer human-readable explanation specific to this
            occurrence.
        instance: Optional URI reference identifying this specific occurrence
            (typically the request path).
        errors: Optional list of per-field validation errors. Not part of
            RFC 7807 but a common extension for 422 responses.
    """

    type: str = Field(default="about:blank")
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    errors: list[dict[str, Any]] | None = None


class APIError(Exception):
    """Raise from anywhere in the app to produce a problem+json response.

    Attributes:
        status_code: HTTP status to return.
        title: Short summary placed in :attr:`ProblemDetail.title`.
        detail: Optional longer explanation.
        type_uri: Stable URI for this error class. Lets dashboards group
            by ``type`` rather than parsing free-text titles.
    """

    def __init__(
        self,
        status_code: int,
        title: str,
        detail: str | None = None,
        type_uri: str = "about:blank",
    ) -> None:
        """Build the exception.

        Args:
            status_code: HTTP status to return to the client.
            title: Short summary of the problem.
            detail: Optional longer human-readable explanation.
            type_uri: Optional stable URI identifying this error class.
        """
        super().__init__(title)
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.type_uri = type_uri


def _problem_response(problem: ProblemDetail) -> JSONResponse:
    """Build a :class:`JSONResponse` carrying a problem+json payload.

    Args:
        problem: The problem object to serialize.

    Returns:
        A :class:`JSONResponse` with the correct ``application/problem+json``
        content type and matching status code.
    """
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(exclude_none=True),
        media_type=PROBLEM_JSON,
    )


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Convert an :class:`APIError` into a problem+json response.

    Args:
        request: The incoming request, used to populate ``instance``.
        exc: The raised :class:`APIError`.

    Returns:
        Problem+json response with the exception's status, title, and detail.
    """
    logger.warning(
        "api_error",
        status=exc.status_code,
        title=exc.title,
        detail=exc.detail,
        path=request.url.path,
    )
    return _problem_response(
        ProblemDetail(
            type=exc.type_uri,
            title=exc.title,
            status=exc.status_code,
            detail=exc.detail,
            instance=request.url.path,
        )
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Convert framework-raised HTTP exceptions (404, 405, ...) to problem+json.

    Args:
        request: The incoming request.
        exc: The exception raised by Starlette / FastAPI.

    Returns:
        Problem+json response mirroring the exception's status code.
    """
    return _problem_response(
        ProblemDetail(
            title=exc.detail if isinstance(exc.detail, str) else "HTTP error",
            status=exc.status_code,
            instance=request.url.path,
        )
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convert Pydantic request-validation failures (422) to problem+json.

    Args:
        request: The incoming request.
        exc: The validation error raised by FastAPI before the route handler ran.

    Returns:
        Problem+json response with per-field errors in the ``errors`` field.
    """
    return _problem_response(
        ProblemDetail(
            title="Request validation failed",
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            instance=request.url.path,
            errors=[
                {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
                for err in exc.errors()
            ],
        )
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected exceptions.

    Logs the full traceback and returns a generic 500 problem+json — never
    leaks internal exception messages to the client.

    Args:
        request: The incoming request.
        exc: Any exception not caught by a more specific handler.

    Returns:
        Problem+json response with status 500 and a generic title.
    """
    logger.exception("unhandled_exception", path=request.url.path, error=str(exc))
    return _problem_response(
        ProblemDetail(
            title="Internal server error",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            instance=request.url.path,
        )
    )


def install_error_handlers(app: FastAPI) -> None:
    """Register all problem+json exception handlers on the given app.

    Idempotent — safe to call from :func:`birthday_tracker.main.create_app`
    even if the app is rebuilt across tests.

    Args:
        app: The FastAPI application to install handlers on.
    """
    app.add_exception_handler(APIError, api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(Exception, unhandled_exception_handler)

from __future__ import annotations

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger()


class NotFoundError(HTTPException):
    def __init__(self, detail: str = "Not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class UnauthorizedError(HTTPException):
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(HTTPException):
    def __init__(self, detail: str = "Forbidden"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class ConflictError(HTTPException):
    def __init__(self, detail: str = "Conflict"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class VllmError(HTTPException):
    def __init__(self, detail: str = "vLLM instance error"):
        super().__init__(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


class QueueFullError(HTTPException):
    def __init__(self, detail: str = "Queue is full, try again later"):
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


class HuggingFaceError(HTTPException):
    def __init__(self, detail: str = "HuggingFace API error"):
        super().__init__(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


def _error_body(request: Request, status_code: int, error: str, message: str) -> JSONResponse:
    request_id = request.headers.get("X-Request-ID", "")
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "message": message, "request_id": request_id},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return _error_body(request, exc.status_code, "http_error", exc.detail or "")


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", exc_info=exc)
    return _error_body(request, 500, "internal_error", "An unexpected error occurred")

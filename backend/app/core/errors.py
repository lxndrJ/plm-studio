from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    status_code = 400
    code = "error"

    def __init__(self, message: str, *, status_code: int | None = None, code: str | None = None, details=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.details = details


class NotFoundError(ApiError):
    status_code = 404
    code = "not_found"


class ConflictError(ApiError):
    status_code = 409
    code = "conflict"


class ForbiddenError(ApiError):
    status_code = 403
    code = "forbidden"


class UnauthorizedError(ApiError):
    status_code = 401
    code = "unauthorized"


class ValidationError(ApiError):
    status_code = 422
    code = "invalid_transition"  # overridden per call site


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code, "details": exc.details},
        )

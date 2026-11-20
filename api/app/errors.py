from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.schemas import StructuredError


class AppError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
        field_errors: dict[str, str] | None = None,
        request_id: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field_errors = field_errors or {}
        self.request_id = request_id
        super().__init__(message)

    def to_schema(self) -> StructuredError:
        return StructuredError(
            code=self.code,
            message=self.message,
            field_errors=self.field_errors,
            request_id=self.request_id,
        )


def _request_id(request: Request) -> str | None:
    return request.headers.get("x-namaa-request-id")


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    if exc.request_id is None:
        exc.request_id = _request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_schema().model_dump(),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    field_errors: dict[str, str] = {}
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ()) if part != "body")
        field_errors[loc or "body"] = err.get("msg", "invalid")
    payload = StructuredError(
        code="validation_failed",
        message="Request failed validation.",
        field_errors=field_errors,
        request_id=_request_id(request),
    )
    return JSONResponse(status_code=422, content=payload.model_dump())


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = {
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        429: "rate_limited",
        503: "service_unavailable",
    }.get(exc.status_code, "http_error")
    payload = StructuredError(
        code=code,
        message=str(exc.detail),
        request_id=_request_id(request),
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

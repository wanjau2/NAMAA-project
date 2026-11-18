from fastapi import Request
from fastapi.responses import JSONResponse

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


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_schema().model_dump(),
    )
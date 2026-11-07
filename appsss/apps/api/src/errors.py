import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from packages.contracts.error import APIError, APIErrorResponse

logger = logging.getLogger(__name__)


class APIException(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        project_id: str | None = None,
        status_code: int = 500,
    ) -> None:
        self.code = code
        self.message = message
        self.project_id = project_id
        self.status_code = status_code


async def api_exception_handler(
    request: Request,
    exc: APIException,
) -> JSONResponse:
    response = APIErrorResponse(
        error=APIError(
            code=exc.code,
            message=exc.message,
            project_id=exc.project_id,
        )
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(exclude_none=True),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    # The envelope stays exactly {"error": {"code", "message"}} (locked
    # by tests); the field-level detail goes to the server log.
    logger.info("Validation failed on %s %s: %s", request.method, request.url.path, exc.errors())
    response = APIErrorResponse(
        error=APIError(
            code="validation_error",
            message="Request validation failed.",
        )
    )

    return JSONResponse(
        status_code=422,
        content=response.model_dump(exclude_none=True),
    )


async def internal_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.error(
        "Unhandled error on %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    response = APIErrorResponse(
        error=APIError(
            code="internal_error",
            message="An internal error occurred.",
        )
    )

    return JSONResponse(
        status_code=500,
        content=response.model_dump(exclude_none=True),
    )

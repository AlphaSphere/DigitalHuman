from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, detail: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}


def success_response(data: object) -> dict:
    return {"success": True, "data": data}


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": {"code": exc.code, "message": exc.message, "detail": exc.detail}},
    )


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": {"code": "HTTP_ERROR", "message": str(exc.detail), "detail": {}}},
    )

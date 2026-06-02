"""
用途：定义统一 API 错误类型与响应包装，使业务层抛错与 HTTP 层返回格式一致。
"""

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """
    用途：业务可预期错误载体，携带错误码、用户可读消息与 HTTP 状态码，供服务层主动抛出。
    """

    def __init__(self, code: str, message: str, status_code: int = 400, detail: dict | None = None) -> None:
        """
        用途：构造一条可被全局处理器捕获的业务异常。

        参数：
            code: 机器可读错误码，前端可用于分支处理
            message: 面向用户或调用方的简短说明
            status_code: HTTP 响应状态码，默认 400
            detail: 附加结构化信息（如字段校验明细），默认空字典
        """
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}


def success_response(data: object) -> dict:
    """
    用途：包装成功响应体，与错误响应的 `{success, error}` 结构对称。

    参数：
        data: 业务载荷，可为 dict、list 或 Pydantic 序列化结果

    返回：
        `{"success": True, "data": ...}` 字典
    """
    return {"success": True, "data": data}


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    """
    用途：FastAPI 异常处理器，将 ApiError 转为统一 JSON 错误响应。

    参数：
        _: 当前请求（未使用）
        exc: 捕获到的 ApiError 实例

    返回：
        含 success=False 与 error 对象的 JSONResponse
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": {"code": exc.code, "message": exc.message, "detail": exc.detail}},
    )


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """
    用途：将 FastAPI/Starlette 原生 HTTPException 也映射为统一错误格式，避免混用多种响应形状。

    参数：
        _: 当前请求（未使用）
        exc: HTTPException，detail 通常为字符串或校验错误列表

    返回：
        code 固定为 HTTP_ERROR 的 JSONResponse
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": {"code": "HTTP_ERROR", "message": str(exc.detail), "detail": {}}},
    )

"""
用途：FastAPI 应用入口，负责生命周期管理、中间件注册与路由挂载，是后端 HTTP 服务的启动点。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import ApiError, api_error_handler, http_error_handler, success_response
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.init_db import ensure_runtime_schema, seed_profiles
from app.db.session import SessionLocal, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    用途：应用启动/关闭生命周期钩子，在首次请求前初始化数据库表与预设配置数据。

    参数：
        _: FastAPI 实例（框架注入，本钩子内未使用）

    逻辑：
        1. 根据 ORM 元数据自动创建缺失的数据表（本地开发便利；生产建议 Alembic）
        2. 打开数据库会话并写入默认音色/数字人预设，避免首次调用 profiles 接口为空
        3. yield 后进入正常运行期；关闭阶段无额外清理
    """
    # 本地开发允许自动建表；生产环境仍建议使用 Alembic migration 管理结构变更。
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema(engine)
    with SessionLocal() as db:
        seed_profiles(db)
    yield


def create_app() -> FastAPI:
    """
    用途：工厂函数，组装日志、配置、异常处理、CORS 与业务路由，供 ASGI 服务器加载。

    返回：
        配置完成的 FastAPI 应用实例

    逻辑：
        1. 初始化日志与全局配置（含存储目录创建）
        2. 注册统一业务异常与 HTTP 异常处理器，保证 API 响应格式一致
        3. 挂载 CORS 中间件与 `/api` 前缀下的业务路由
        4. 注册 `/health` 探活端点供负载均衡与容器编排使用
    """
    configure_logging()
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    @app.middleware("http")
    async def enforce_api_key(request: Request, call_next):
        """
        用途：为 `/api` 前缀下的所有接口提供可选的共享密钥校验。

        逻辑：
            1. `api_auth_token` 未配置（默认空字符串）时完全放行，保持现有本地/桌面单机使用体验不变
            2. 配置后，非 `/api` 前缀的请求（如 `/health`、文档）不受影响
            3. `/api` 请求必须携带匹配的 `X-API-Key` header，否则返回 401
        """
        if settings.api_auth_token and request.url.path.startswith(settings.api_prefix):
            if request.headers.get("X-API-Key") != settings.api_auth_token:
                return JSONResponse(status_code=401, content={"error": {"code": "UNAUTHORIZED", "message": "缺少或错误的 X-API-Key"}})
        return await call_next(request)

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health")
    def health() -> dict:
        """
        用途：健康检查接口，供运维与编排系统确认服务进程可用。

        返回：
            统一成功包装下的 `{"status": "ok"}` 结构
        """
        return success_response({"status": "ok"})

    return app


app = create_app()

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import ApiError, api_error_handler, http_error_handler, success_response
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.init_db import seed_profiles
from app.db.session import SessionLocal, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 本地开发允许自动建表；生产环境仍建议使用 Alembic migration 管理结构变更。
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_profiles(db)
    yield


def create_app() -> FastAPI:
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
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health")
    def health() -> dict:
        return success_response({"status": "ok"})

    return app


app = create_app()

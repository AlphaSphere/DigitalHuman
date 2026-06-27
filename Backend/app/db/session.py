"""
用途：数据库引擎与会话工厂，以及 FastAPI 依赖 `get_db`，贯穿所有需要持久化的 API 与启动脚本。
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()
_engine_kwargs: dict = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    # FastAPI 多线程访问 SQLite 时需要关闭同线程校验
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(settings.database_url, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """
    用途：请求级数据库会话依赖，保证每个 HTTP 请求独立会话并在结束后关闭连接。

    返回：
        生成器 yield 的 SQLAlchemy Session

    逻辑：
        1. 从 SessionLocal 创建会话并 yield 给路由/服务层
        2. finally 中 close，避免连接泄漏（无论业务是否抛错）
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

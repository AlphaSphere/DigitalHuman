"""
用途：SQLAlchemy 声明式基类与时间戳混入，为所有 ORM 模型提供统一的 metadata 与 created/updated 字段。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


metadata = MetaData()


class Base(DeclarativeBase):
    """用途：ORM 模型基类，绑定全局 MetaData，供 Alembic 与 create_all 发现表结构。"""

    metadata = metadata


class TimestampMixin:
    """用途：为实体提供 created_at / updated_at 自动维护，用于任务与分发等需审计时间的表。"""

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


JsonDict = dict[str, Any]

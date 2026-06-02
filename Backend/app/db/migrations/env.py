"""
用途：Alembic 迁移运行环境，绑定应用配置中的数据库 URL 与 ORM metadata，供 CLI 升级/降级表结构。
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base
from app.db import models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    用途：离线模式执行迁移（仅生成 SQL 脚本，不建立真实连接），用于 CI 或 DBA 审阅。

    逻辑：
        1. 从配置读取 URL，literal_binds 使 SQL 可直接输出到 stdout
        2. 在单事务中 run_migrations
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    用途：在线模式连接数据库并应用迁移 revision，本地与容器部署的常规路径。

    逻辑：
        1. 从 alembic.ini 段创建引擎，NullPool 避免迁移进程长期占用连接池
        2. 绑定 connection 后于事务内执行 run_migrations
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

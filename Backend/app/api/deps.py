"""
用途：FastAPI 依赖注入聚合模块，向路由层暴露可复用的 Depends 工厂（如数据库会话）。
"""

from app.db.session import get_db

__all__ = ["get_db"]

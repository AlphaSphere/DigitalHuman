"""
用途：顶层 API 路由注册表，将各业务子路由挂载到统一 APIRouter，由 main 以 `/api` 前缀 include。
"""

from fastapi import APIRouter

from app.api.routers import artifacts, distributions, music, profiles, risk_checks, segments, tasks

api_router = APIRouter()
api_router.include_router(tasks.router, tags=["tasks"])
api_router.include_router(segments.router, tags=["segments"])
api_router.include_router(profiles.router, tags=["profiles"])
api_router.include_router(risk_checks.router, tags=["risk-checks"])
api_router.include_router(artifacts.router, tags=["artifacts"])
api_router.include_router(music.router, tags=["music"])
api_router.include_router(distributions.router, tags=["distributions"])

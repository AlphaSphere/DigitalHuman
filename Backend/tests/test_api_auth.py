"""覆盖 app/main.py 里 X-API-Key 共享密钥中间件：默认放行、配置后强制校验。"""

import os

# 必须在导入 app.main（进而导入 app.db.session 建 engine）之前设置，
# 用 sqlite 避免测试依赖真实 MySQL/Redis。
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["API_AUTH_TOKEN"] = "test-secret-token"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.main import create_app  # noqa: E402


def test_api_requires_key_when_configured():
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/api/system/runtime-info")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_api_accepts_matching_key():
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/api/system/runtime-info", headers={"X-API-Key": "test-secret-token"})
        assert resp.status_code == 200


def test_api_rejects_wrong_key():
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/api/system/runtime-info", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401


def test_health_endpoint_bypasses_auth():
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200


def test_default_empty_token_leaves_api_open():
    os.environ["API_AUTH_TOKEN"] = ""
    get_settings.cache_clear()
    try:
        app = create_app()
        with TestClient(app) as client:
            resp = client.get("/api/system/runtime-info")
            assert resp.status_code == 200
    finally:
        os.environ["API_AUTH_TOKEN"] = "test-secret-token"
        get_settings.cache_clear()

import os
import tempfile

os.environ.setdefault("BANK_DB", os.path.join(tempfile.gettempdir(), "bankmind_test.db"))

import pytest


@pytest.fixture(autouse=True)
def fresh_env():
    from app.data import database
    from app.security import circuit
    from app.agents.coordinator import SESSIONS
    from app.middleware.rate_limit import limiter

    database.reset_and_seed()
    circuit._state.clear()
    SESSIONS.clear()
    limiter.requests.clear()  # 重置限流器
    yield


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c


def chat(client, message, user_id="u001"):
    return client.post("/api/chat", json={"user_id": user_id, "message": message}).json()


def mfa_code_of(res):
    import re

    m = re.search(r"(\d{6})", res.get("mfa_hint") or "")
    assert m, f"未找到演示验证码: {res}"
    return m.group(1)

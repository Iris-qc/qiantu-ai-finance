"""pytest 公共设施：独立测试库（PostgreSQL，默认 csaifm_test），每个用例清空数据。"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://csaifm:csaifm@localhost:5433/csaifm_test")
os.environ.setdefault("AI_MODE", "demo")  # 测试固定演示模式，不依赖外部服务

from app.core.deps import get_db  # noqa: E402
from app.db.session import Base  # noqa: E402
from app.main import app  # noqa: E402
from app import models  # noqa: E402,F401
from app.seed import ensure_builtins  # noqa: E402

TEST_URL = os.environ["DATABASE_URL"]

engine = create_engine(TEST_URL, pool_pre_ping=True)
TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def _clean():
    """每个用例前清空业务表（保留内置分类）。"""
    with engine.begin() as conn:
        for t in ("notifications", "reports", "goals", "budgets", "bills",
                  "profiles", "password_reset_codes", "categories", "users"):
            conn.execute(text(f'TRUNCATE "{t}" RESTART IDENTITY CASCADE'))
    with TestSession() as db:
        ensure_builtins(db)
        db.commit()
    yield


@pytest.fixture
def db_session():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register(client, username="alice", password="Passw0rd123", email=None) -> dict:
    resp = client.post("/api/auth/register", json={
        "username": username, "password": password,
        "email": email or f"{username}@example.com",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user1(client):
    """已注册并完成财务初始化的用户。"""
    data = register(client)
    token = data["access_token"]
    client.put("/api/profile/init", json={
        "initial_assets_cents": 500000, "allowance_cents": 200000, "allowance_day": 1,
    }, headers=auth_header(token))
    return {"token": token, "id": data["user"]["id"]}


@pytest.fixture
def user2(client):
    data = register(client, username="bob2026", password="Passw0rd456")
    return {"token": data["access_token"], "id": data["user"]["id"]}


def make_bill(client, token, *, bill_type="expense", amount_cents=1000, category_id=None,
              occurred_at=None, note=None, categories=None):
    if category_id is None:
        if categories is None:
            categories = client.get("/api/categories", headers=auth_header(token)).json()
        cat = next(c for c in categories if c["kind"] == bill_type)
        category_id = cat["id"]
    return client.post("/api/bills", json={
        "bill_type": bill_type, "amount_cents": amount_cents, "category_id": category_id,
        "occurred_at": occurred_at, "note": note,
    }, headers=auth_header(token))

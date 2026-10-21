"""注册 / 登录 / 锁定 / 会话。"""
from .conftest import auth_header, register


def test_register_and_login(client):
    data = register(client)
    assert data["user"]["username"] == "alice"
    assert data["token_type"] == "bearer"
    # 登录成功
    r = client.post("/api/auth/login", json={"username": "alice", "password": "Passw0rd123"})
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers=auth_header(r.json()["access_token"]))
    assert me.status_code == 200 and me.json()["username"] == "alice"


def test_duplicate_username(client):
    register(client)
    r = client.post("/api/auth/register", json={
        "username": "alice", "password": "Passw0rd999", "email": "other@example.com"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "USERNAME_TAKEN"


def test_duplicate_email(client):
    register(client, username="alice", email="same@example.com")
    r = client.post("/api/auth/register", json={
        "username": "bob2026", "password": "Passw0rd999", "email": "same@example.com"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "EMAIL_TAKEN"


def test_email_required(client):
    # 缺省或空邮箱均应在 schema 校验阶段被拒绝（SRS 3.3.1.1 注册输入项）
    r = client.post("/api/auth/register", json={
        "username": "dave", "password": "Passw0rd123"})
    assert r.status_code == 422
    r = client.post("/api/auth/register", json={
        "username": "dave", "password": "Passw0rd123", "email": ""})
    assert r.status_code == 422


def test_weak_password_rejected(client):
    r = client.post("/api/auth/register", json={
        "username": "carol", "password": "short1", "email": "carol@example.com"})
    assert r.status_code == 422
    r = client.post("/api/auth/register", json={
        "username": "carol", "password": "onlyletters", "email": "carol@example.com"})
    assert r.status_code == 422


def test_login_wrong_password(client):
    register(client)
    r = client.post("/api/auth/login", json={"username": "alice", "password": "wrongpass1"})
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "BAD_CREDENTIALS"


def test_login_lockout_after_3_failures(client):
    register(client)
    for _ in range(3):
        client.post("/api/auth/login", json={"username": "alice", "password": "wrongpass1"})
    # 第 4 次即使密码正确也被锁定
    r = client.post("/api/auth/login", json={"username": "alice", "password": "Passw0rd123"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "ACCOUNT_LOCKED"


def test_unauthorized_no_token(client):
    assert client.get("/api/profile").status_code == 401
    assert client.get("/api/bills").status_code == 401


def test_invalid_token(client):
    r = client.get("/api/bills", headers=auth_header("not-a-token"))
    assert r.status_code == 401

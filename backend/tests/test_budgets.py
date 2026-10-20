"""预算：覆盖式更新、使用率、状态、提醒去重与回落、月底预测。"""
from datetime import date, timedelta

from .conftest import auth_header, make_bill


def _this_month() -> str:
    return date.today().strftime("%Y-%m")


def _notifs(client, token):
    return client.get("/api/notifications", headers=auth_header(token)).json()


def test_budget_usage_and_status(client, user1):
    token = user1["token"]
    month = _this_month()
    cats = client.get("/api/categories", headers=auth_header(token)).json()
    food = next(c for c in cats if c["name"] == "餐饮")
    client.put("/api/budgets", json={
        "month": month, "scope": "category", "category_id": food["id"],
        "amount_cents": 10000, "threshold_percent": 80,
    }, headers=auth_header(token))
    make_bill(client, token, amount_cents=3000, category_id=food["id"])

    r = client.get("/api/budgets", params={"month": month}, headers=auth_header(token))
    item = r.json()["items"][0]
    assert item["spent_cents"] == 3000
    assert item["usage_percent"] == 30
    assert item["status"] == "normal"

    make_bill(client, token, amount_cents=6000, category_id=food["id"])
    r = client.get("/api/budgets", params={"month": month}, headers=auth_header(token))
    item = r.json()["items"][0]
    assert item["usage_percent"] == 90
    assert item["status"] == "approaching"

    make_bill(client, token, amount_cents=2000, category_id=food["id"])
    r = client.get("/api/budgets", params={"month": month}, headers=auth_header(token))
    item = r.json()["items"][0]
    assert item["usage_percent"] == 110
    assert item["status"] == "exceeded"


def test_budget_upsert_overwrites(client, user1):
    token = user1["token"]
    client.put("/api/budgets", json={"month": _this_month(), "scope": "total",
                                     "amount_cents": 100000}, headers=auth_header(token))
    client.put("/api/budgets", json={"month": _this_month(), "scope": "total",
                                     "amount_cents": 200000}, headers=auth_header(token))
    r = client.get("/api/budgets", params={"month": _this_month()}, headers=auth_header(token))
    assert len(r.json()["items"]) == 1
    assert r.json()["items"][0]["amount_cents"] == 200000


def test_budget_notification_dedup_and_clear(client, user1):
    token = user1["token"]
    month = _this_month()
    client.put("/api/budgets", json={"month": month, "scope": "total", "amount_cents": 10000,
                                     "threshold_percent": 80}, headers=auth_header(token))
    cats = client.get("/api/categories", headers=auth_header(token)).json()
    exp = next(c for c in cats if c["kind"] == "expense")
    # 超过阈值：多次操作只产生一条提醒
    for _ in range(3):
        make_bill(client, token, amount_cents=4000, category_id=exp["id"])
    ns = _notifs(client, token)
    budget_ns = [n for n in ns["items"] if n["kind"] == "budget"]
    assert len(budget_ns) == 1
    assert budget_ns[0]["level"] == "danger"

    # 消费回落到阈值以下（删除账单）→ 提醒清除
    bills = client.get("/api/bills", headers=auth_header(token)).json()["items"]
    for b in bills:
        client.delete(f"/api/bills/{b['id']}", headers=auth_header(token))
    ns = _notifs(client, token)
    assert not [n for n in ns["items"] if n["kind"] == "budget"]


def test_forecast_numbers(client, user1):
    token = user1["token"]
    month = _this_month()
    client.put("/api/budgets", json={"month": month, "scope": "total", "amount_cents": 50000},
               headers=auth_header(token))
    cats = client.get("/api/categories", headers=auth_header(token)).json()
    exp = next(c for c in cats if c["kind"] == "expense")
    make_bill(client, token, amount_cents=5000, category_id=exp["id"])  # 均匀分散不可行，用一笔

    r = client.get("/api/budgets", params={"month": month}, headers=auth_header(token))
    f = r.json()["forecast"]
    assert f["spent_cents"] == 5000
    assert f["days_total"] > 0
    assert f["days_elapsed"] == date.today().day
    # predicted = spent + spent/elapsed * remaining
    expected = 5000 + (5000 // date.today().day) * f["days_remaining"]
    assert f["predicted_cents"] == expected
    assert f["risk"] in ("none", "potential", "high", "no_budget")


def test_budget_validation(client, user1):
    token = user1["token"]
    # 阈值超出 50-100
    r = client.put("/api/budgets", json={"month": _this_month(), "scope": "total",
                                         "amount_cents": 100, "threshold_percent": 10},
                   headers=auth_header(token))
    assert r.status_code == 422
    # 分类预算缺 category_id
    r = client.put("/api/budgets", json={"month": _this_month(), "scope": "category",
                                         "amount_cents": 100}, headers=auth_header(token))
    assert r.status_code == 422
    # 收入分类不能设预算
    cats = client.get("/api/categories", headers=auth_header(token)).json()
    inc = next(c for c in cats if c["kind"] == "income")
    r = client.put("/api/budgets", json={"month": _this_month(), "scope": "category",
                                         "category_id": inc["id"], "amount_cents": 100},
                   headers=auth_header(token))
    assert r.status_code == 400

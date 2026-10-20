"""账单增删改 → 资产重算；资产校准；初始化规则。"""
from .conftest import auth_header, make_bill, register


def _assets(client, token) -> int:
    return client.get("/api/profile", headers=auth_header(token)).json()["current_assets_cents"]


def test_init_and_asset_recompute(client, user1):
    assert _assets(client, user1["token"]) == 500000
    cats = client.get("/api/categories", headers=auth_header(user1["token"])).json()
    # 收入 2000 元
    make_bill(client, user1["token"], bill_type="income", amount_cents=200000, categories=cats)
    assert _assets(client, user1["token"]) == 700000
    # 支出 2550 分
    r = make_bill(client, user1["token"], bill_type="expense", amount_cents=2550, categories=cats)
    assert r.status_code == 201
    assert _assets(client, user1["token"]) == 700000 - 2550
    bill_id = r.json()["id"]

    # 修改金额 → 重算
    r = client.patch(f"/api/bills/{bill_id}", json={"amount_cents": 1050},
                     headers=auth_header(user1["token"]))
    assert r.status_code == 200
    assert _assets(client, user1["token"]) == 700000 - 1050

    # 删除 → 资产还原
    assert client.delete(f"/api/bills/{bill_id}", headers=auth_header(user1["token"])).status_code == 204
    assert _assets(client, user1["token"]) == 700000


def test_init_twice_rejected(client, user1):
    r = client.put("/api/profile/init", json={
        "initial_assets_cents": 999, "allowance_cents": 1, "allowance_day": 1,
    }, headers=auth_header(user1["token"]))
    assert r.status_code == 409


def test_calibrate_creates_adjustment_bill(client, user1):
    token = user1["token"]
    cats = client.get("/api/categories", headers=auth_header(token)).json()
    make_bill(client, token, bill_type="expense", amount_cents=12345, categories=cats)
    before = _assets(client, token)
    # 用户说实际资产是 10000 元（1000000 分）
    r = client.post("/api/profile/calibrate", json={"actual_assets_cents": 1000000},
                    headers=auth_header(token))
    assert r.status_code == 200
    assert r.json()["current_assets_cents"] == 1000000
    # 校准账单可追溯
    bills = client.get("/api/bills", params={"bill_type": "adjustment"},
                       headers=auth_header(token)).json()
    assert bills["total"] == 1
    adj = bills["items"][0]
    assert adj["amount_cents"] == 1000000 - before
    assert adj["category_name"] == "资产校准"
    # 删除校准账单 → 资产回到计算值
    client.delete(f"/api/bills/{adj['id']}", headers=auth_header(token))
    assert _assets(client, token) == before


def test_calibrate_no_change_rejected(client, user1):
    r = client.post("/api/profile/calibrate", json={"actual_assets_cents": 500000},
                    headers=auth_header(user1["token"]))
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "NO_CHANGE"


def test_calibrate_before_init_rejected(client):
    data = register(client, username="dave")
    r = client.post("/api/profile/calibrate", json={"actual_assets_cents": 100},
                    headers=auth_header(data["access_token"]))
    assert r.status_code == 409


def test_bill_category_mismatch(client, user1):
    cats = client.get("/api/categories", headers=auth_header(user1["token"])).json()
    income_cat = next(c for c in cats if c["kind"] == "income")
    r = make_bill(client, user1["token"], bill_type="expense", amount_cents=100,
                  category_id=income_cat["id"])
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "CATEGORY_MISMATCH"


def test_bill_filters(client, user1):
    token = user1["token"]
    cats = client.get("/api/categories", headers=auth_header(token)).json()
    make_bill(client, token, bill_type="expense", amount_cents=1000, note="麦当劳薯条", categories=cats)
    make_bill(client, token, bill_type="expense", amount_cents=2000, note="买书", categories=cats)
    make_bill(client, token, bill_type="income", amount_cents=3000, categories=cats)

    r = client.get("/api/bills", params={"keyword": "薯条"}, headers=auth_header(token))
    assert r.json()["total"] == 1
    r = client.get("/api/bills", params={"bill_type": "income"}, headers=auth_header(token))
    assert r.json()["total"] == 1
    r = client.get("/api/bills", params={"start": "2020-01-01", "end": "2020-01-02"},
                   headers=auth_header(token))
    assert r.json()["total"] == 0

"""用户数据隔离：接口不能访问其他用户的账单/报告/目标。"""
from .conftest import auth_header, make_bill, register


def test_bill_isolation(client, user1, user2):
    cats1 = client.get("/api/categories", headers=auth_header(user1["token"])).json()
    r = make_bill(client, user1["token"], bill_type="expense", amount_cents=5000, categories=cats1)
    bill_id = r.json()["id"]
    assert bill_id

    # 用户 B 看不到、改不了、删不掉
    assert client.get("/api/bills", headers=auth_header(user2["token"])).json()["total"] == 0
    assert client.get(f"/api/bills/{bill_id}", headers=auth_header(user2["token"])).status_code == 404
    assert client.patch(f"/api/bills/{bill_id}", json={"amount_cents": 1},
                        headers=auth_header(user2["token"])).status_code == 404
    assert client.delete(f"/api/bills/{bill_id}", headers=auth_header(user2["token"])).status_code == 404
    # 原账单还在
    assert client.get(f"/api/bills/{bill_id}", headers=auth_header(user1["token"])).status_code == 200


def test_goal_and_report_isolation(client, user1, user2):
    g = client.post("/api/goals", json={
        "name": "A的目标", "target_cents": 10000, "current_cents": 0, "deadline": "2027-01-01",
    }, headers=auth_header(user1["token"])).json()
    assert client.patch(f"/api/goals/{g['id']}", json={"current_cents": 100},
                        headers=auth_header(user2["token"])).status_code == 404
    assert client.delete(f"/api/goals/{g['id']}", headers=auth_header(user2["token"])).status_code == 404

    rep = client.post("/api/reports/generate", json={"report_type": "monthly"},
                      headers=auth_header(user1["token"])).json()
    assert client.get(f"/api/reports/{rep['id']}", headers=auth_header(user2["token"])).status_code == 404
    assert client.get(f"/api/reports/{rep['id']}/pdf", headers=auth_header(user2["token"])).status_code == 404


def test_custom_category_isolation(client, user1, user2):
    r = client.post("/api/categories", json={"name": "宠物", "kind": "expense"},
                    headers=auth_header(user1["token"]))
    cat_id = r.json()["id"]
    # B 看不到 A 的自定义分类
    names = [c["name"] for c in client.get("/api/categories", headers=auth_header(user2["token"])).json()]
    assert "宠物" not in names
    # B 不能改/删 A 的分类
    assert client.patch(f"/api/categories/{cat_id}", json={"name": "宠物2", "kind": "expense"},
                        headers=auth_header(user2["token"])).status_code == 404
    assert client.delete(f"/api/categories/{cat_id}", headers=auth_header(user2["token"])).status_code == 404

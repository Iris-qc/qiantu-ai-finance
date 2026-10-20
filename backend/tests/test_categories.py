"""分类：内置保护、自定义增删改、删除后历史账单保留名称。"""
from .conftest import auth_header, make_bill


def test_builtin_categories_exist(client, user1):
    cats = client.get("/api/categories", headers=auth_header(user1["token"])).json()
    names = {c["name"] for c in cats}
    for n in ("餐饮", "交通", "学习", "娱乐", "网购", "生活用品", "生活费", "兼职"):
        assert n in names


def test_builtin_cannot_delete_or_rename(client, user1):
    token = user1["token"]
    cats = client.get("/api/categories", headers=auth_header(token)).json()
    builtin = next(c for c in cats if c["is_builtin"])
    assert client.delete(f"/api/categories/{builtin['id']}",
                         headers=auth_header(token)).status_code == 403
    assert client.patch(f"/api/categories/{builtin['id']}",
                        json={"name": "改名", "kind": "expense"},
                        headers=auth_header(token)).status_code == 403


def test_custom_category_lifecycle_keeps_history(client, user1):
    token = user1["token"]
    r = client.post("/api/categories", json={"name": "宠物", "kind": "expense"},
                    headers=auth_header(token))
    assert r.status_code == 201
    cat_id = r.json()["id"]

    # 重名拒绝
    assert client.post("/api/categories", json={"name": "宠物", "kind": "expense"},
                       headers=auth_header(token)).status_code == 400
    # 与内置重名拒绝
    assert client.post("/api/categories", json={"name": "餐饮", "kind": "expense"},
                       headers=auth_header(token)).status_code == 400

    # 记一笔账单后删除分类：历史账单仍显示原分类名称
    r = make_bill(client, token, amount_cents=8888, category_id=cat_id)
    bill_id = r.json()["id"]
    assert client.delete(f"/api/categories/{cat_id}", headers=auth_header(token)).status_code == 204

    bill = client.get(f"/api/bills/{bill_id}", headers=auth_header(token)).json()
    assert bill["category_name"] == "宠物"

    # 已删除分类不能再用于新账单
    assert make_bill(client, token, amount_cents=100, category_id=cat_id).status_code == 400
    # 分类列表不再出现
    names = [c["name"] for c in client.get("/api/categories", headers=auth_header(token)).json()]
    assert "宠物" not in names


def test_rename_category(client, user1):
    token = user1["token"]
    r = client.post("/api/categories", json={"name": "手办", "kind": "expense"},
                    headers=auth_header(token))
    cat_id = r.json()["id"]
    r = client.patch(f"/api/categories/{cat_id}", json={"name": "收藏", "kind": "expense"},
                     headers=auth_header(token))
    assert r.status_code == 200 and r.json()["name"] == "收藏"

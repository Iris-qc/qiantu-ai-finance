"""自然语言草稿：解析 → 确认批量入库；失败不得改变任何正式数据。"""
from .conftest import auth_header, make_bill


def test_nl_parse_demo(client, user1):
    token = user1["token"]
    r = client.post("/api/ai/drafts/nl", json={"text": "今天奶茶18，打车25"},
                    headers=auth_header(token))
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "demo"
    assert "演示模式" in body["notice"]
    assert len(body["items"]) == 2
    amounts = {i["amount_cents"] for i in body["items"]}
    assert amounts == {1800, 2500}
    # 解析不写库
    assert client.get("/api/bills", headers=auth_header(token)).json()["total"] == 0


def test_nl_parse_garbage(client, user1):
    r = client.post("/api/ai/drafts/nl", json={"text": "今天天气不错"},
                    headers=auth_header(user1["token"]))
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "PARSE_FAILED"


def test_confirm_drafts_creates_bills(client, user1):
    token = user1["token"]
    cats = client.get("/api/categories", headers=auth_header(token)).json()
    food = next(c for c in cats if c["name"] == "餐饮")
    r = client.post("/api/ai/drafts/confirm", json={
        "source": "nlp",
        "items": [
            {"bill_type": "expense", "amount_cents": 1800, "category_id": food["id"],
             "category_name": "餐饮", "note": "奶茶"},
            {"bill_type": "expense", "amount_cents": 2500, "category_name": "交通",
             "occurred_at": None, "note": "打车"},
        ],
    }, headers=auth_header(token))
    assert r.status_code == 201
    ids = r.json()["created"]
    assert len(ids) == 2
    bills = client.get("/api/bills", headers=auth_header(token)).json()
    assert bills["total"] == 2
    assert all(b["source"] == "nlp" for b in bills["items"])
    # 资产联动
    assert client.get("/api/profile", headers=auth_header(token)).json()["current_assets_cents"] == \
        500000 - 1800 - 2500


def test_confirm_invalid_draft_writes_nothing(client, user1):
    token = user1["token"]
    cats = client.get("/api/categories", headers=auth_header(token)).json()
    food = next(c for c in cats if c["name"] == "餐饮")
    r = client.post("/api/ai/drafts/confirm", json={
        "source": "nlp",
        "items": [
            {"bill_type": "expense", "amount_cents": 1800, "category_id": food["id"],
             "category_name": "餐饮"},
            {"bill_type": "expense", "amount_cents": 9999, "category_name": "不存在的分类"},
        ],
    }, headers=auth_header(token))
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "DRAFT_VALIDATION_FAILED"
    # 一条都没写入（整体拒绝）
    assert client.get("/api/bills", headers=auth_header(token)).json()["total"] == 0
    assert client.get("/api/profile", headers=auth_header(token)).json()["current_assets_cents"] == 500000


def test_speech_and_image_unconfigured(client, user1):
    """未配置外部服务时，语音/图片接口必须明确返回"未配置"。"""
    r = client.post("/api/ai/drafts/speech",
                    files={"file": ("a.webm", b"fake-audio", "audio/webm")},
                    headers=auth_header(user1["token"]))
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "SERVICE_NOT_CONFIGURED"

    r = client.post("/api/ai/drafts/image",
                    files={"file": ("a.jpg", b"fake-image", "image/jpeg")},
                    headers=auth_header(user1["token"]))
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "SERVICE_NOT_CONFIGURED"


def test_advice_uses_real_data_only(client, user1):
    token = user1["token"]
    cats = client.get("/api/categories", headers=auth_header(token)).json()
    make_bill(client, token, amount_cents=3000, categories=cats)
    r = client.post("/api/ai/advice", json={"question": "这个月还能买500元的鞋吗"},
                    headers=auth_header(token))
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "demo"
    assert body["answer"]
    assert len(body["basis"]) >= 3
    assert any("当前资产" in b["label"] for b in body["basis"])
    assert "仅供理财参考" in body["disclaimer"]

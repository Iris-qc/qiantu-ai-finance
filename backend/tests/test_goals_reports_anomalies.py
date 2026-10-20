"""储蓄目标、异常消费提醒、报告与 PDF。"""
from datetime import date, timedelta

from .conftest import auth_header, make_bill


def test_goal_metrics(client, user1):
    token = user1["token"]
    r = client.post("/api/goals", json={
        "name": "买电脑", "target_cents": 400000, "current_cents": 100000,
        "deadline": (date.today() + timedelta(days=30)).isoformat(),
    }, headers=auth_header(token))
    assert r.status_code == 201
    g = r.json()
    assert g["progress_percent"] == 25
    assert g["remaining_cents"] == 300000
    assert g["days_left"] == 30
    assert g["suggested_daily_cents"] == 10000  # 300000/30
    # 更新已存金额
    r = client.patch(f"/api/goals/{g['id']}", json={"current_cents": 200000},
                     headers=auth_header(token))
    assert r.json()["progress_percent"] == 50
    # 逾期目标
    r = client.post("/api/goals", json={
        "name": "过期目标", "target_cents": 100000, "current_cents": 0,
        "deadline": (date.today() - timedelta(days=1)).isoformat(),
    }, headers=auth_header(token))
    assert r.json()["risk"] == "overdue"
    # 目标逾期产生提醒
    ns = client.get("/api/notifications", headers=auth_header(token)).json()
    assert any(n["kind"] == "goal" for n in ns["items"])


def test_anomaly_single_bill(client, user1):
    token = user1["token"]
    cats = client.get("/api/categories", headers=auth_header(token)).json()
    # 超过 300 元单笔阈值
    r = make_bill(client, token, amount_cents=49900, categories=cats)
    assert r.status_code == 201
    ns = client.get("/api/notifications", headers=auth_header(token)).json()
    anoms = [n for n in ns["items"] if n["kind"] == "anomaly"]
    assert len(anoms) >= 1
    assert any(n["bill_id"] == r.json()["id"] for n in anoms)

    # 小金额不触发
    make_bill(client, token, amount_cents=500, categories=cats)
    ns = client.get("/api/notifications", headers=auth_header(token)).json()
    assert len([n for n in ns["items"] if n["kind"] == "anomaly"]) == len(anoms)


def test_anomaly_dedup_on_repeat(client, user1):
    token = user1["token"]
    cats = client.get("/api/categories", headers=auth_header(token)).json()
    r = make_bill(client, token, amount_cents=49900, categories=cats)
    bill_id = r.json()["id"]
    # 多次编辑同一笔账单不产生重复提醒
    for _ in range(2):
        client.patch(f"/api/bills/{bill_id}", json={"note": "改备注"},
                     headers=auth_header(token))
    ns = client.get("/api/notifications", headers=auth_header(token)).json()
    assert len([n for n in ns["items"] if n["kind"] == "anomaly" and n["bill_id"] == bill_id]) == 1


def test_report_monthly_and_pdf(client, user1):
    token = user1["token"]
    cats = client.get("/api/categories", headers=auth_header(token)).json()
    make_bill(client, token, amount_cents=12000, categories=cats)
    make_bill(client, token, bill_type="income", amount_cents=200000, categories=cats)

    month = date.today().strftime("%Y-%m")
    r = client.post("/api/reports/generate", json={"report_type": "monthly",
                                                   "period_start": month},
                    headers=auth_header(token))
    assert r.status_code == 201
    rep = r.json()
    assert rep["content"]["summary"]["expense_cents"] == 12000
    assert rep["content"]["summary"]["income_cents"] == 200000
    assert rep["content"]["categories"][0]["amount_cents"] == 12000

    # 列表与详情
    lst = client.get("/api/reports", headers=auth_header(token)).json()
    assert lst["items"][0]["id"] == rep["id"]
    assert client.get(f"/api/reports/{rep['id']}", headers=auth_header(token)).status_code == 200

    # PDF 真实生成并可下载
    pdf = client.get(f"/api/reports/{rep['id']}/pdf", headers=auth_header(token))
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:5] == b"%PDF-"
    # 再次下载走缓存（has_pdf 变 True）
    assert client.get(f"/api/reports/{rep['id']}", headers=auth_header(token)).json()["has_pdf"]


def test_report_period_options(client, user1):
    r = client.get("/api/reports/periods", headers=auth_header(user1["token"]))
    assert r.status_code == 200
    body = r.json()
    assert len(body["monthly"]) == 12
    assert len(body["semesters"]) >= 1
    assert body["years"]


def test_notification_read(client, user1):
    token = user1["token"]
    cats = client.get("/api/categories", headers=auth_header(token)).json()
    make_bill(client, token, amount_cents=49900, categories=cats)
    ns = client.get("/api/notifications", headers=auth_header(token)).json()
    assert ns["unread_count"] >= 1
    nid = ns["items"][0]["id"]
    assert client.post(f"/api/notifications/{nid}/read",
                       headers=auth_header(token)).json()["read_at"]
    ns = client.get("/api/notifications", params={"unread_only": True},
                    headers=auth_header(token)).json()
    assert all(i["id"] != nid for i in ns["items"])
    # 全部已读
    client.post("/api/notifications/read-all", headers=auth_header(token))
    assert client.get("/api/notifications", headers=auth_header(token)).json()["unread_count"] == 0

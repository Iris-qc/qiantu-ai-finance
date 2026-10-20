"""CSAIFM 端到端验证：真实 API 全流程。

前提：后端已运行在 http://127.0.0.1:8000（需先执行 alembic upgrade head 与 python -m app.seed）。
运行（backend 目录下）：
    .venv\\Scripts\\python.exe scripts\\e2e.py        # Windows
    .venv/bin/python scripts/e2e.py                   # Linux/macOS
覆盖：注册→初始化→记账增删改→资产重算核对→用户数据隔离(404)→
      未配置外部服务(503)→演示模式解析/建议→演示账号分析/提醒/报告生成→PDF 下载。
"""
import random
import sys

import httpx

B = "http://127.0.0.1:8000"
# trust_env=False：不走系统代理（本机代理配置会拦截 127.0.0.1 请求）
c = httpx.Client(base_url=B, timeout=30, trust_env=False)
results = []


def check(label, cond, detail=""):
    results.append(cond)
    print(f"{'PASS' if cond else 'FAIL'}  {label}  {detail}")
    return cond


# 1) 健康检查
r = c.get("/healthz")
check("healthz", r.status_code == 200 and r.json()["status"] == "ok")

# 2) 注册 -> 初始化
u = "e2e" + str(random.randint(1000, 9999))
r = c.post("/api/auth/register", json={"username": u, "password": "Passw0rd123"})
tok = r.json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}
check("register", r.status_code == 201, u)
r = c.put("/api/profile/init", headers=h,
          json={"initial_assets_cents": 100000, "allowance_cents": 150000, "allowance_day": 1})
check("profile init", r.status_code == 200)

# 3) 分类与记账
r = c.get("/api/categories", headers=h)
cats = r.json()
food = next(x["id"] for x in cats if x["kind"] == "expense")
check("categories", len(cats) >= 7, f"{len(cats)} items, first expense id={food}")

r = c.post("/api/bills", headers=h,
           json={"bill_type": "expense", "amount_cents": 1850, "category_id": food, "note": "dinner"})
bid = r.json()["id"]
check("bill create", r.status_code == 201, f"id={bid}")

# 4) 资产实时重算：创建 / 编辑 / 删除
r = c.get("/api/profile", headers=h)
check("assets after create = 98150", r.json()["current_assets_cents"] == 98150,
      str(r.json()["current_assets_cents"]))
r = c.patch(f"/api/bills/{bid}", headers=h,
            json={"bill_type": "expense", "amount_cents": 2350, "category_id": food})
check("bill edit", r.status_code == 200)
r = c.get("/api/profile", headers=h)
check("assets after edit = 97650", r.json()["current_assets_cents"] == 97650,
      str(r.json()["current_assets_cents"]))
r = c.delete(f"/api/bills/{bid}", headers=h)
check("bill delete 204", r.status_code == 204)
r = c.get("/api/profile", headers=h)
check("assets after delete = 100000", r.json()["current_assets_cents"] == 100000,
      str(r.json()["current_assets_cents"]))

# 5) 用户数据隔离：他人账单返回 404
r2 = c.post("/api/auth/register", json={"username": "iso" + str(random.randint(1000, 9999)),
                                        "password": "Passw0rd456"})
h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}
r = c.get("/api/bills/1", headers=h2)
check("isolation: foreign bill -> 404", r.status_code == 404, str(r.status_code))

# 6) 未配置的外部服务明确返回 503
r = c.post("/api/ai/drafts/speech", headers=h,
           files={"file": ("t.webm", b"\x00" * 64, "audio/webm")})
check("speech unconfigured -> 503", r.status_code == 503, str(r.status_code))
r = c.post("/api/ai/drafts/image", headers=h,
           files={"file": ("t.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "image/png")})
check("ocr unconfigured -> 503", r.status_code == 503, str(r.status_code))

# 7) 演示模式自然语言解析 + 消费建议（如实标注 demo）
r = c.post("/api/ai/drafts/nl", headers=h, json={"text": "今天奶茶18打车25，收了红包50"})
d = r.json()
check("nl demo parse", r.status_code == 200 and d["mode"] == "demo" and len(d["items"]) >= 2,
      f"mode={d.get('mode')} items={len(d.get('items', []))}")
r = c.post("/api/ai/advice", headers=h, json={"question": "这个月还能花多少钱"})
d = r.json()
check("advice demo", r.status_code == 200 and d["mode"] == "demo",
      f"mode={d.get('mode')} warnings={len(d.get('warnings', []))}")

# 8) 演示账号：分析 / 预算 / 提醒 / 报告 + PDF
r = c.post("/api/auth/login", json={"username": "demo", "password": "Demo123456"})
hd = {"Authorization": f"Bearer {r.json()['access_token']}"}
check("demo login", r.status_code == 200)
r = c.get("/api/analytics/trend", headers=hd, params={"granularity": "day", "start": "2026-09-01", "end": "2026-10-18"})
check("demo analytics trend", r.status_code == 200 and len(r.json()["points"]) > 0,
      f"{len(r.json().get('points', []))} points")
r = c.get("/api/notifications", headers=hd)
check("demo notifications", r.status_code == 200, f"{len(r.json().get('items', []))} items")
r = c.get("/api/reports/periods", headers=hd)
check("demo report periods", r.status_code == 200)
r = c.post("/api/reports/generate", headers=hd, json={"report_type": "monthly", "period_start": "2026-10"})
rid = r.json()["id"]
check("report generate", r.status_code == 201, f"id={rid}")
r = c.get(f"/api/reports/{rid}/pdf", headers=hd)
check("report pdf download", r.status_code == 200 and r.content[:4] == b"%PDF",
      f"{len(r.content)} bytes")

print()
print("E2E RESULT:", "ALL PASS" if all(results) else "HAS FAILURES")
sys.exit(0 if all(results) else 1)

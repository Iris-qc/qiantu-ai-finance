"""资产计算：当前资产 = 初始资产基数 + Σ收入 − Σ支出 + Σ校准差额。

账单每次新增/修改/删除后全量重算（单用户账单量级下 O(n) 汇总足够），
保证编辑删除后资产始终正确。生活费发放日不自动增加资产。
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Bill, Profile

ADJUSTMENT_CATEGORY = "资产校准"


def asset_breakdown(db: Session, user_id: int) -> dict:
    rows = db.execute(
        select(Bill.bill_type, func.coalesce(func.sum(Bill.amount_cents), 0))
        .where(Bill.user_id == user_id)
        .group_by(Bill.bill_type)
    ).all()
    by_type = dict(rows)
    income = int(by_type.get("income", 0))
    expense = int(by_type.get("expense", 0))
    adjustment = int(by_type.get("adjustment", 0))
    return {"income": income, "expense": expense, "adjustment": adjustment}


def current_assets(db: Session, user_id: int) -> int:
    profile = db.execute(select(Profile).where(Profile.user_id == user_id)).scalar_one()
    b = asset_breakdown(db, user_id)
    base = profile.initial_assets_cents if profile.initialized else 0
    return base + b["income"] - b["expense"] + b["adjustment"]

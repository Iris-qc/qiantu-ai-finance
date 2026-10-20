"""预算与超支预测。

口径（与 README 一致）：
- 预算使用率 = 周期内该范围已支出 ÷ 预算金额 × 100%（四舍五入取整）。
- 状态：usage < 阈值 → normal；阈值 ≤ usage ≤ 100% → approaching；> 100% → exceeded。
- 月底预测：预测期末消费 = 当月已支出 + 日均消费 × 剩余天数；日均消费 = 已支出 ÷ 已过天数。
- 风险：预测 ≤ 预算 → none；预算 < 预测 ≤ 预算×1.2 → potential；预测 > 预算×1.2 → high。
- 提醒去重：同一预算同一状态只有一条未读提醒；状态回落（低于阈值）即删除。
"""
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.money import cents_to_yuan
from ..core.timeutil import app_tz, month_start, next_month_start, now
from ..models import Bill, Budget
from .notify import clear_notification, upsert_notification

RISK_LABELS = {
    "none": "无超支风险",
    "potential": "潜在超支风险",
    "high": "高超支风险",
    "no_budget": "未设置总预算",
}


def month_key(d: date) -> str:
    return d.strftime("%Y-%m")


def _spent_for_scope(db: Session, user_id: int, ms: datetime, budget: Budget) -> int:
    me = next_month_start(ms)
    q = select(func.coalesce(func.sum(Bill.amount_cents), 0)).where(
        Bill.user_id == user_id,
        Bill.bill_type == "expense",
        Bill.occurred_at >= ms,
        Bill.occurred_at < me,
    )
    if budget.scope == "category":
        q = q.where(Bill.category_id == budget.category_id)
    return int(db.execute(q).scalar_one())


def budget_usage(db: Session, user_id: int, ms: datetime, budget: Budget) -> tuple[int, int, str]:
    spent = _spent_for_scope(db, user_id, ms, budget)
    usage = int(round(spent * 100 / budget.amount_cents)) if budget.amount_cents else 0
    if usage <= 100 and usage < budget.threshold_percent:
        status = "normal"
    elif usage <= 100:
        status = "approaching"
    else:
        status = "exceeded"
    return spent, usage, status


def _sync_budget_notification(db: Session, user_id: int, budget: Budget,
                              usage: int, status: str, spent: int) -> None:
    """仅为当月预算同步提醒，避免历史月份反复提醒。"""
    if month_key(budget.month_start) != month_key(now().date()):
        return
    key = f"budget:{budget.id}"
    label = "总预算" if budget.scope == "total" else f"「{budget.category_name}」分类预算"
    if status == "normal":
        clear_notification(db, user_id, key)
        return
    if status == "approaching":
        upsert_notification(
            db, user_id, kind="budget", level="warning", dedup_key=key,
            title=f"{label}接近上限",
            content=f"{label}已使用 {usage}%（预警阈值 {budget.threshold_percent}%），"
                    f"已支出 {cents_to_yuan(spent)} 元，请留意控制消费。",
        )
    else:
        upsert_notification(
            db, user_id, kind="budget", level="danger", dedup_key=key,
            title=f"{label}已超支",
            content=f"{label}使用率达到 {usage}%，已支出 {cents_to_yuan(spent)} 元，"
                    f"已超出预算额度 {cents_to_yuan(budget.amount_cents)} 元，建议暂停非必要消费。",
        )


def sync_budget_for_month(db: Session, user_id: int, month: date) -> None:
    """账单变更后重算该月全部预算并同步提醒。"""
    ms = month_start(month)
    budgets = db.execute(
        select(Budget).where(Budget.user_id == user_id, Budget.month_start == ms.date())
    ).scalars().all()
    for b in budgets:
        spent, usage, status = budget_usage(db, user_id, ms, b)
        _sync_budget_notification(db, user_id, b, usage, status, spent)


def forecast(db: Session, user_id: int, month: date) -> dict:
    """月底超支预测（基于当月已支出与消费速率）。"""
    ms = month_start(month)
    me = next_month_start(month)
    days_total = (me.astimezone(app_tz()).date() - ms.astimezone(app_tz()).date()).days
    spent = int(db.execute(
        select(func.coalesce(func.sum(Bill.amount_cents), 0)).where(
            Bill.user_id == user_id, Bill.bill_type == "expense",
            Bill.occurred_at >= ms, Bill.occurred_at < me,
        )
    ).scalar_one())

    today = now().date()
    if ms.astimezone(app_tz()).date() > today:  # 未来月份
        days_elapsed, days_remaining = 0, days_total
    elif me.astimezone(app_tz()).date() <= today:  # 已过去的月份
        days_elapsed, days_remaining = days_total, 0
    else:
        days_elapsed = today.day
        days_remaining = days_total - today.day

    avg_daily = spent // days_elapsed if days_elapsed else 0
    predicted = spent + avg_daily * days_remaining

    total_budget = db.execute(
        select(Budget).where(
            Budget.user_id == user_id, Budget.month_start == ms.date(), Budget.scope == "total"
        )
    ).scalar_one_or_none()

    s = get_settings()
    if total_budget is None:
        risk, risk_label, budget_cents = "no_budget", RISK_LABELS["no_budget"], None
    elif predicted <= total_budget.amount_cents:
        risk, risk_label, budget_cents = "none", RISK_LABELS["none"], total_budget.amount_cents
    elif predicted <= int(total_budget.amount_cents * s.forecast_high_risk_factor):
        risk, risk_label, budget_cents = "potential", RISK_LABELS["potential"], total_budget.amount_cents
    else:
        risk, risk_label, budget_cents = "high", RISK_LABELS["high"], total_budget.amount_cents

    return {
        "days_total": days_total, "days_elapsed": days_elapsed, "days_remaining": days_remaining,
        "avg_daily_cents": avg_daily, "spent_cents": spent, "predicted_cents": predicted,
        "budget_cents": budget_cents, "risk": risk, "risk_label": risk_label,
    }


def overview(db: Session, user_id: int, month: date) -> dict:
    ms = month_start(month)
    budgets = db.execute(
        select(Budget).where(Budget.user_id == user_id, Budget.month_start == ms.date())
        .order_by(Budget.scope.desc(), Budget.id)
    ).scalars().all()
    items = []
    for b in budgets:
        spent, usage, status = budget_usage(db, user_id, ms, b)
        items.append({
            "id": b.id, "scope": b.scope, "category_id": b.category_id,
            "category_name": b.category_name, "amount_cents": b.amount_cents,
            "spent_cents": spent, "usage_percent": usage,
            "threshold_percent": b.threshold_percent, "status": status,
        })
    return {"month": month_key(month), "items": items, "forecast": forecast(db, user_id, month)}

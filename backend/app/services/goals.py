"""储蓄目标派生指标。

口径（与 README 一致）：
- 完成度 = 当前已存 ÷ 目标金额 × 100%（四舍五入）。
- 建议每日储蓄 = 剩余金额 ÷ 剩余天数（剩余天数 ≥1；已逾期/已完成时为 0）。
- 建议每月储蓄 = 剩余金额 ÷ 剩余月数（剩余月数 = ceil(剩余天数/30)，最少 1）。
- 风险：已完成 done；已逾期 overdue；剩余天数内每日需存 > 每月生活费的 1/30 × 0.5 → tight；否则 on_track。
"""
import math
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.timeutil import now
from ..models import Goal, Profile
from .notify import clear_notification, upsert_notification


def goal_metrics(g: Goal, allowance_cents: int) -> dict:
    today = now().date()
    progress = int(round(g.current_cents * 100 / g.target_cents)) if g.target_cents else 0
    remaining = max(0, g.target_cents - g.current_cents)
    days_left = (g.deadline - today).days
    if days_left <= 0:
        suggested_daily = 0
        suggested_monthly = 0
    else:
        suggested_daily = math.ceil(remaining / days_left)
        suggested_monthly = math.ceil(remaining / max(math.ceil(days_left / 30), 1))

    if progress >= 100:
        risk = "done"
    elif days_left < 0:
        risk = "overdue"
    elif suggested_daily > allowance_cents // 30 // 2:
        risk = "tight"
    else:
        risk = "on_track"
    return {
        "progress_percent": progress, "remaining_cents": remaining, "days_left": days_left,
        "suggested_daily_cents": suggested_daily, "suggested_monthly_cents": suggested_monthly,
        "risk": risk,
    }


def sync_goal_notification(db: Session, g: Goal, metrics: dict) -> None:
    key = f"goal:{g.id}"
    if metrics["risk"] == "done":
        clear_notification(db, g.user_id, key)
    elif metrics["risk"] == "overdue":
        upsert_notification(
            db, g.user_id, kind="goal", level="danger", dedup_key=key,
            title=f"储蓄目标「{g.name}」已逾期",
            content=f"目标截止日期已过，当前完成 {metrics['progress_percent']}%，"
                    f"还剩 {metrics['remaining_cents'] / 100:.2f} 元未完成。可延长截止日期或调整目标金额。",
        )
    elif metrics["risk"] == "tight":
        upsert_notification(
            db, g.user_id, kind="goal", level="warning", dedup_key=key,
            title=f"储蓄目标「{g.name}」达成有难度",
            content=f"距截止还有 {metrics['days_left']} 天，需每天存约 "
                    f"{metrics['suggested_daily_cents'] / 100:.2f} 元才能按时达成，请合理安排。",
        )
    else:
        clear_notification(db, g.user_id, key)


def allowance_for(db: Session, user_id: int) -> int:
    p = db.execute(select(Profile).where(Profile.user_id == user_id)).scalar_one_or_none()
    return p.allowance_cents if p else 0

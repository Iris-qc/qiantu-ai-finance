"""异常消费识别。

口径（与 README 一致）：
- 单笔异常：支出金额 > 单笔阈值（默认 300 元）；或近 30 天有效样本 ≥5 笔且金额 > 3 倍近 30 天单笔均值。
- 日消费异常：当日支出 > 2 倍近 30 天日均支出，且当日支出 > 100 元。
- 历史不足时仅按单笔绝对阈值判断。提醒按 (单笔: 账单ID / 日: 日期) 去重，条件解除即删除。
"""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.money import cents_to_yuan
from ..core.timeutil import app_tz, local_date
from ..models import Bill
from .notify import clear_notification, upsert_notification


def _recent_expense_stats(db: Session, user_id: int, since: datetime, exclude_bill_id: int | None) -> dict:
    q = select(
        func.count(Bill.id),
        func.coalesce(func.avg(Bill.amount_cents), 0),
    ).where(
        Bill.user_id == user_id, Bill.bill_type == "expense", Bill.occurred_at >= since,
    )
    if exclude_bill_id is not None:
        q = q.where(Bill.id != exclude_bill_id)
    cnt, avg = db.execute(q).one()
    return {"count": int(cnt), "avg_single": int(float(avg))}


def _recent_daily_stats(db: Session, user_id: int, since: datetime, exclude_day: datetime) -> dict:
    """近 window 天日均支出（排除指定日）。"""
    s = get_settings()
    day_start = exclude_day.astimezone(app_tz()).replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    total = db.execute(
        select(func.coalesce(func.sum(Bill.amount_cents), 0)).where(
            Bill.user_id == user_id, Bill.bill_type == "expense",
            Bill.occurred_at >= since, Bill.occurred_at < day_end,
            Bill.occurred_at < day_start,
        )
    ).scalar_one() or 0
    # 简化：用总金额/窗口天数作为日均（排除当天后的近似）
    return {"avg_daily": int(total / s.anomaly_window_days)}


def _day_total(db: Session, user_id: int, day: datetime) -> int:
    day_start = day.astimezone(app_tz()).replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    return int(db.execute(
        select(func.coalesce(func.sum(Bill.amount_cents), 0)).where(
            Bill.user_id == user_id, Bill.bill_type == "expense",
            Bill.occurred_at >= day_start, Bill.occurred_at < day_end,
        )
    ).scalar_one())


def evaluate_bill(db: Session, bill: Bill) -> None:
    """账单新增/修改后评估异常；同事务执行，随账单一起提交/回滚。"""
    if bill.bill_type != "expense":
        return
    s = get_settings()
    user_id = bill.user_id
    since = bill.occurred_at - timedelta(days=s.anomaly_window_days)
    key_bill = f"anomaly:bill:{bill.id}"
    key_day = f"anomaly:day:{local_date(bill.occurred_at)}"

    # —— 单笔异常 ——
    stats = _recent_expense_stats(db, user_id, since, exclude_bill_id=bill.id)
    triggered = bill.amount_cents > s.anomaly_single_cents
    reason_parts = []
    if triggered:
        reason_parts.append(f"单笔金额 {cents_to_yuan(bill.amount_cents)} 元超过单笔阈值 {cents_to_yuan(s.anomaly_single_cents)} 元")
    elif stats["count"] >= s.anomaly_single_min_samples and stats["avg_single"] > 0 \
            and bill.amount_cents > int(stats["avg_single"] * s.anomaly_single_factor):
        triggered = True
        reason_parts.append(
            f"单笔金额 {cents_to_yuan(bill.amount_cents)} 元超过近 {s.anomaly_window_days} 天单笔均值"
            f"（{cents_to_yuan(stats['avg_single'])} 元）的 {s.anomaly_single_factor:g} 倍"
        )
    if triggered:
        upsert_notification(
            db, user_id, kind="anomaly", level="danger", dedup_key=key_bill,
            title="异常消费提醒：单笔金额偏高",
            content=f"「{bill.category_name}」账单 {cents_to_yuan(bill.amount_cents)} 元（{local_date(bill.occurred_at)}）"
                    f"被识别为异常消费：{'；'.join(reason_parts)}。请核对是否为误记或冲动消费。",
            bill_id=bill.id,
        )
    else:
        clear_notification(db, user_id, key_bill)

    # —— 日消费异常 ——
    day_total = _day_total(db, user_id, bill.occurred_at)
    daily = _recent_daily_stats(db, user_id, since, exclude_day=bill.occurred_at)
    if daily["avg_daily"] > 0 and day_total > s.anomaly_daily_floor_cents \
            and day_total > int(daily["avg_daily"] * s.anomaly_daily_factor):
        upsert_notification(
            db, user_id, kind="anomaly", level="warning", dedup_key=key_day,
            title="异常消费提醒：当日消费明显偏高",
            content=f"{local_date(bill.occurred_at)} 当日支出已达 {cents_to_yuan(day_total)} 元，"
                    f"超过近 {s.anomaly_window_days} 天日均（约 {cents_to_yuan(daily['avg_daily'])} 元）的 "
                    f"{s.anomaly_daily_factor:g} 倍，请注意控制当日消费。",
            bill_id=bill.id,
        )
    else:
        clear_notification(db, user_id, key_day)


def cleanup_for_deleted_bill(db: Session, bill: Bill) -> None:
    """删除账单后清除其触发的提醒（若日提醒仍被其它账单支撑则保留）。"""
    clear_notification(db, bill.user_id, f"anomaly:bill:{bill.id}")
    if bill.bill_type == "expense":
        day_total = _day_total(db, bill.user_id, bill.occurred_at)
        s = get_settings()
        daily = _recent_daily_stats(
            db, bill.user_id, bill.occurred_at - timedelta(days=s.anomaly_window_days),
            exclude_day=bill.occurred_at,
        )
        if not (daily["avg_daily"] > 0 and day_total > s.anomaly_daily_floor_cents
                and day_total > int(daily["avg_daily"] * s.anomaly_daily_factor)):
            clear_notification(db, bill.user_id, f"anomaly:day:{local_date(bill.occurred_at)}")

"""消费分析：日/周/月趋势、分类占比、周期汇总与环比。"""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core import timeutil
from ..core.deps import get_current_user, get_db
from ..core.errors import biz_error
from ..models import Bill, User
from ..schemas.analytics import CategoryOut, CategoryShare, SummaryOut, TrendOut, TrendPoint

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _bounds(start: date | None, end: date | None, default_days: int = 30) -> tuple[datetime, datetime]:
    tz = timeutil.app_tz()
    if start and end and start > end:
        raise biz_error("INVALID_RANGE", "开始日期不能晚于结束日期")
    e = end or timeutil.now().date()
    s = start or (e - timedelta(days=default_days - 1))
    start_dt = datetime(s.year, s.month, s.day, tzinfo=tz)
    end_dt = datetime(e.year, e.month, e.day, tzinfo=tz) + timedelta(days=1)
    return start_dt, end_dt


def _expense_income(db: Session, user_id: int, start_dt: datetime, end_dt: datetime) -> dict:
    rows = db.execute(
        select(Bill.bill_type, func.sum(Bill.amount_cents), Bill.occurred_at)
        .where(Bill.user_id == user_id, Bill.bill_type.in_(["income", "expense"]),
               Bill.occurred_at >= start_dt, Bill.occurred_at < end_dt)
        .group_by(Bill.bill_type, Bill.occurred_at)
    ).all()
    return rows


@router.get("/trend", response_model=TrendOut)
def trend(
    granularity: str = Query(default="day", pattern="^(day|week|month)$"),
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_dt, end_dt = _bounds(start, end)
    rows = db.execute(
        select(Bill.bill_type, func.sum(Bill.amount_cents), Bill.occurred_at)
        .where(Bill.user_id == user.id, Bill.bill_type.in_(["income", "expense"]),
               Bill.occurred_at >= start_dt, Bill.occurred_at < end_dt)
        .group_by(Bill.bill_type, Bill.occurred_at)
    ).all()
    # 按粒度分桶（业务时区）
    buckets: dict[str, dict] = {}
    for btype, total, occ in rows:
        local = timeutil.as_app_tz(occ)
        if granularity == "day":
            key = local.strftime("%Y-%m-%d")
        elif granularity == "week":
            iso = local.isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
        else:
            key = local.strftime("%Y-%m")
        b = buckets.setdefault(key, {"expense": 0, "income": 0})
        b["expense" if btype == "expense" else "income"] += int(total or 0)

    # 填充区间内所有桶（空桶补 0）
    points: list[TrendPoint] = []
    if granularity == "day":
        d = start_dt.astimezone(timeutil.app_tz()).date()
        last = (end_dt - timedelta(days=1)).astimezone(timeutil.app_tz()).date()
        while d <= last:
            k = d.isoformat()
            b = buckets.get(k, {"expense": 0, "income": 0})
            points.append(TrendPoint(label=d.strftime("%m-%d"), expense_cents=b["expense"],
                                     income_cents=b["income"]))
            d += timedelta(days=1)
    elif granularity == "week":
        d = start_dt.astimezone(timeutil.app_tz()).date()
        last = (end_dt - timedelta(days=1)).astimezone(timeutil.app_tz()).date()
        seen = set()
        while d <= last:
            iso = d.isocalendar()
            k = f"{iso[0]}-W{iso[1]:02d}"
            if k not in seen:
                seen.add(k)
                b = buckets.get(k, {"expense": 0, "income": 0})
                points.append(TrendPoint(label=f"{d.strftime('%m-%d')}周", expense_cents=b["expense"],
                                         income_cents=b["income"]))
            d += timedelta(days=7)
    else:
        d = start_dt.astimezone(timeutil.app_tz()).date().replace(day=1)
        last = (end_dt - timedelta(days=1)).astimezone(timeutil.app_tz()).date().replace(day=1)
        while d <= last:
            k = d.strftime("%Y-%m")
            b = buckets.get(k, {"expense": 0, "income": 0})
            points.append(TrendPoint(label=k, expense_cents=b["expense"], income_cents=b["income"]))
            d = (d + timedelta(days=32)).replace(day=1)
    return TrendOut(granularity=granularity, points=points)


@router.get("/categories", response_model=CategoryOut)
def categories(start: date | None = None, end: date | None = None,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    start_dt, end_dt = _bounds(start, end)
    rows = db.execute(
        select(Bill.category_name, func.sum(Bill.amount_cents))
        .where(Bill.user_id == user.id, Bill.bill_type == "expense",
               Bill.occurred_at >= start_dt, Bill.occurred_at < end_dt)
        .group_by(Bill.category_name).order_by(func.sum(Bill.amount_cents).desc())
    ).all()
    total = sum(int(a) for _, a in rows)
    items = [
        CategoryShare(category_name=n, amount_cents=int(a),
                      percent=round(a * 100 / total, 1) if total else 0.0)
        for n, a in rows
    ]
    return CategoryOut(items=items, total_cents=total)


@router.get("/summary", response_model=SummaryOut)
def summary(start: date | None = None, end: date | None = None,
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    start_dt, end_dt = _bounds(start, end)
    rows = db.execute(
        select(Bill.bill_type, func.sum(Bill.amount_cents), func.count(Bill.id))
        .where(Bill.user_id == user.id, Bill.bill_type.in_(["income", "expense"]),
               Bill.occurred_at >= start_dt, Bill.occurred_at < end_dt)
        .group_by(Bill.bill_type)
    ).all()
    totals = {bt: (int(a), int(c)) for bt, a, c in rows}
    exp, exp_n = totals.get("expense", (0, 0))
    inc, inc_n = totals.get("income", (0, 0))

    top_cat = db.execute(
        select(Bill.category_name)
        .where(Bill.user_id == user.id, Bill.bill_type == "expense",
               Bill.occurred_at >= start_dt, Bill.occurred_at < end_dt)
        .group_by(Bill.category_name).order_by(func.sum(Bill.amount_cents).desc()).limit(1)
    ).scalar_one_or_none()

    # 上一同长周期（环比）
    length = end_dt - start_dt
    prev_rows = db.execute(
        select(Bill.bill_type, func.sum(Bill.amount_cents))
        .where(Bill.user_id == user.id, Bill.bill_type.in_(["income", "expense"]),
               Bill.occurred_at >= start_dt - length, Bill.occurred_at < start_dt)
        .group_by(Bill.bill_type)
    ).all()
    prev = {bt: int(a) for bt, a in prev_rows}

    return SummaryOut(
        period_start=start_dt.astimezone(timeutil.app_tz()).date().isoformat(),
        period_end=(end_dt - timedelta(days=1)).astimezone(timeutil.app_tz()).date().isoformat(),
        expense_cents=exp, income_cents=inc, bill_count=exp_n + inc_n,
        top_category=top_cat,
        prev_expense_cents=prev.get("expense", 0), prev_income_cents=prev.get("income", 0),
    )

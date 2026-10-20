"""账单：查询/搜索/筛选、新增、修改、删除。

每次增删改在同一事务内联动：资产重算（读时全量汇总，无需维护冗余字段）、
当月预算使用与提醒同步、异常消费评估。账单按用户严格隔离。
"""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..core import timeutil
from ..core.deps import clamp_page, get_current_user, get_db
from ..core.errors import biz_error, not_found
from ..models import Bill, Category, User
from ..schemas.bill import BillIn, BillListOut, BillOut, BillUpdateIn
from ..services import anomalies, budgets

router = APIRouter(prefix="/bills", tags=["bills"])


def _resolve_category(db: Session, user_id: int, category_id: int, bill_type: str) -> Category:
    cat = db.get(Category, category_id)
    if cat is None or cat.deleted_at is not None:
        raise biz_error("CATEGORY_NOT_FOUND", "分类不存在或已删除")
    if cat.user_id is not None and cat.user_id != user_id:
        raise biz_error("CATEGORY_NOT_FOUND", "分类不存在")
    if cat.kind != bill_type:
        raise biz_error("CATEGORY_MISMATCH",
                        f"「{cat.name}」是{'收入' if cat.kind == 'income' else '支出'}分类，"
                        f"不能用于{'收入' if bill_type == 'income' else '支出'}账单")
    return cat


def _own_bill(db: Session, user: User, bill_id: int) -> Bill:
    bill = db.get(Bill, bill_id)
    if bill is None or bill.user_id != user.id:
        raise not_found("账单不存在")
    return bill


def _as_aware(dt: datetime | None) -> datetime:
    if dt is None:
        return timeutil.now()
    return timeutil.as_app_tz(dt)


@router.get("", response_model=BillListOut)
def list_bills(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    bill_type: str | None = Query(default=None, pattern="^(income|expense|adjustment)$"),
    category_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    keyword: str | None = Query(default=None, max_length=50),
    page: int = 1,
    page_size: int = 20,
    sort: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    page, page_size = clamp_page(page, page_size)
    q = select(Bill).where(Bill.user_id == user.id)
    if bill_type:
        q = q.where(Bill.bill_type == bill_type)
    if category_id:
        q = q.where(Bill.category_id == category_id)
    if start:
        q = q.where(Bill.occurred_at >= timeutil.as_app_tz(datetime.combine(start, time.min)))
    if end:
        q = q.where(Bill.occurred_at < timeutil.as_app_tz(datetime.combine(end + timedelta(days=1), time.min)))
    if keyword:
        like = f"%{keyword}%"
        q = q.where(or_(Bill.category_name.ilike(like), Bill.note.ilike(like)))
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    order = Bill.occurred_at.desc() if sort == "desc" else Bill.occurred_at.asc()
    items = db.execute(q.order_by(order, Bill.id.desc()).offset((page - 1) * page_size)
                       .limit(page_size)).scalars().all()
    return BillListOut(
        items=[BillOut.model_validate(b) for b in items],
        total=total, page=page, page_size=page_size,
    )


def _write_bill(db: Session, user_id: int, *, bill_type: str, amount_cents: int,
                category_id: int, occurred_at: datetime, note: str | None,
                source: str = "manual") -> Bill:
    cat = _resolve_category(db, user_id, category_id, bill_type)
    bill = Bill(
        user_id=user_id, bill_type=bill_type, amount_cents=amount_cents,
        category_id=cat.id, category_name=cat.name,
        occurred_at=_as_aware(occurred_at), note=note, source=source,
    )
    db.add(bill)
    db.flush()
    budgets.sync_budget_for_month(db, user_id, timeutil.local_date(bill.occurred_at))
    anomalies.evaluate_bill(db, bill)
    return bill


@router.post("", response_model=BillOut, status_code=201)
def create_bill(body: BillIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    bill = _write_bill(
        db, user.id, bill_type=body.bill_type, amount_cents=body.amount_cents,
        category_id=body.category_id, occurred_at=body.occurred_at, note=body.note,
    )
    db.commit()
    db.refresh(bill)
    return bill


@router.get("/{bill_id}", response_model=BillOut)
def get_bill(bill_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _own_bill(db, user, bill_id)


@router.patch("/{bill_id}", response_model=BillOut)
def update_bill(bill_id: int, body: BillUpdateIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    bill = _own_bill(db, user, bill_id)
    if bill.bill_type == "adjustment":
        raise biz_error("ADJUSTMENT_IMMUTABLE", "资产校准记录不可直接编辑，请使用「资产校准」重新校正")

    old_month = timeutil.local_date(bill.occurred_at)
    new_type = body.bill_type or bill.bill_type
    new_category_id = body.category_id if body.category_id is not None else bill.category_id
    new_amount = body.amount_cents if body.amount_cents is not None else bill.amount_cents
    cat = _resolve_category(db, user.id, new_category_id, new_type) \
        if new_category_id is not None else None
    if cat is not None:
        bill.category_name = cat.name
    bill.bill_type = new_type
    bill.amount_cents = new_amount
    if cat is not None:
        bill.category_id = cat.id
    if body.occurred_at is not None:
        bill.occurred_at = _as_aware(body.occurred_at)
    if body.note is not None:
        bill.note = body.note

    new_month = timeutil.local_date(bill.occurred_at)
    db.flush()
    for m in {old_month.replace(day=1), new_month.replace(day=1)}:
        budgets.sync_budget_for_month(db, user.id, m)
    anomalies.evaluate_bill(db, bill)
    db.commit()
    db.refresh(bill)
    return bill


@router.delete("/{bill_id}", status_code=204)
def delete_bill(bill_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bill = _own_bill(db, user, bill_id)
    month = timeutil.local_date(bill.occurred_at)
    anomalies.cleanup_for_deleted_bill(db, bill)
    db.delete(bill)
    db.flush()
    budgets.sync_budget_for_month(db, user.id, month)
    db.commit()

"""预算：月度总预算与分类预算（覆盖式更新）、使用率、提醒、月底超支预测。"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import timeutil
from ..core.deps import get_current_user, get_db
from ..core.errors import biz_error, not_found
from ..core.timeutil import parse_date
from ..models import Budget, Category, User
from ..schemas.budget import BudgetOverviewOut, BudgetUpsertIn
from ..services import budgets as budget_svc

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=BudgetOverviewOut)
def get_budgets(
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = parse_date(month + "-01") if month else timeutil.now().date()
    return budget_svc.overview(db, user.id, m)


@router.put("", response_model=BudgetOverviewOut)
def upsert_budget(body: BudgetUpsertIn, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    ms = parse_date(body.month + "-01")
    if body.scope == "category":
        cat = db.get(Category, body.category_id)
        if cat is None or cat.deleted_at is not None:
            raise biz_error("CATEGORY_NOT_FOUND", "分类不存在或已删除")
        if cat.user_id is not None and cat.user_id != user.id:
            raise biz_error("CATEGORY_NOT_FOUND", "分类不存在")
        if cat.kind != "expense":
            raise biz_error("CATEGORY_MISMATCH", "预算仅支持支出分类")
        cat_name = cat.name
    else:
        cat_name = None

    existing = db.execute(
        select(Budget).where(
            Budget.user_id == user.id, Budget.month_start == ms,
            Budget.scope == body.scope, Budget.category_id == body.category_id,
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = Budget(
            user_id=user.id, month_start=ms, scope=body.scope,
            category_id=body.category_id, category_name=cat_name,
            amount_cents=body.amount_cents, threshold_percent=body.threshold_percent,
        )
        db.add(existing)
    else:
        existing.amount_cents = body.amount_cents
        existing.threshold_percent = body.threshold_percent
        existing.category_name = cat_name
    db.flush()
    # 立即同步该月提醒（新增/修改预算都会改变预警状态）
    budget_svc.sync_budget_for_month(db, user.id, ms)
    db.commit()
    return budget_svc.overview(db, user.id, ms)


@router.delete("/{budget_id}", status_code=204)
def delete_budget(budget_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    b = db.get(Budget, budget_id)
    if b is None or b.user_id != user.id:
        raise not_found("预算不存在")
    from ..services.notify import clear_notification
    clear_notification(db, user.id, f"budget:{b.id}")
    db.delete(b)
    db.commit()

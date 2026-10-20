"""用户财务档案：初始化 / 修改生活费配置 / 资产校准。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import timeutil
from ..core.deps import get_current_user, get_db
from ..core.errors import biz_error
from ..core.money import cents_to_yuan
from ..models import Bill, Profile, User
from ..schemas.profile import CalibrateIn, ProfileEmailIn, ProfileInitIn, ProfileOut, ProfileUpdateIn
from ..schemas.auth import RegisterIn
from ..services.assets import ADJUSTMENT_CATEGORY, asset_breakdown, current_assets

router = APIRouter(prefix="/profile", tags=["profile"])


def _get_or_create_profile(db: Session, user_id: int) -> Profile:
    p = db.execute(select(Profile).where(Profile.user_id == user_id)).scalar_one_or_none()
    if p is None:
        p = Profile(user_id=user_id)
        db.add(p)
        db.flush()
    return p


def _to_out(db: Session, user_id: int, p: Profile) -> ProfileOut:
    b = asset_breakdown(db, user_id)
    base = p.initial_assets_cents if p.initialized else 0
    cur = base + b["income"] - b["expense"] + b["adjustment"]
    today = timeutil.now().date()
    days = timeutil.days_to_next_allowance(p.allowance_day, today)
    nxt = timeutil.next_allowance_date(p.allowance_day, today)
    suggested = cur // max(days, 1) if p.initialized and cur > 0 else 0
    return ProfileOut(
        initialized=p.initialized, initial_assets_cents=base, allowance_cents=p.allowance_cents,
        allowance_day=p.allowance_day, current_assets_cents=cur,
        total_income_cents=b["income"], total_expense_cents=b["expense"],
        adjustment_cents=b["adjustment"], days_to_next_allowance=days,
        next_allowance_date=nxt, suggested_daily_cents=suggested,
    )


@router.get("", response_model=ProfileOut)
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _get_or_create_profile(db, user.id)
    db.commit()
    return _to_out(db, user.id, p)


@router.put("/init", response_model=ProfileOut)
def init_profile(body: ProfileInitIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    p = _get_or_create_profile(db, user.id)
    if p.initialized:
        raise biz_error("ALREADY_INITIALIZED",
                        "财务资料已初始化，资产基数不可重复设置；如资产有偏差请使用「资产校准」", 409)
    p.initialized = True
    p.initial_assets_cents = body.initial_assets_cents
    p.allowance_cents = body.allowance_cents
    p.allowance_day = body.allowance_day
    db.commit()
    return _to_out(db, user.id, p)


@router.put("", response_model=ProfileOut)
def update_profile(body: ProfileUpdateIn, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """修改生活费金额与发放日（发放日只用于周期计算，不会自动增加资产）。"""
    p = _get_or_create_profile(db, user.id)
    p.allowance_cents = body.allowance_cents
    p.allowance_day = body.allowance_day
    db.commit()
    return _to_out(db, user.id, p)


@router.post("/calibrate", response_model=ProfileOut)
def calibrate(body: CalibrateIn, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    """资产校准：按用户录入的实际资产生成一条可追溯的校准账单，并重算资产。"""
    p = _get_or_create_profile(db, user.id)
    if not p.initialized:
        raise biz_error("NOT_INITIALIZED", "请先完成财务资料初始化", 409)
    cur = current_assets(db, user.id)
    delta = body.actual_assets_cents - cur
    if delta == 0:
        raise biz_error("NO_CHANGE", f"当前资产已是 {cents_to_yuan(cur)} 元，无需校准")
    bill = Bill(
        user_id=user.id, bill_type="adjustment", amount_cents=delta,
        category_id=None, category_name=ADJUSTMENT_CATEGORY,
        occurred_at=timeutil.now(), source="manual",
        note=f"资产校准：用户录入实际资产 {cents_to_yuan(body.actual_assets_cents)} 元"
             f"（原计算值 {cents_to_yuan(cur)} 元，差额 {cents_to_yuan(delta)} 元）",
    )
    db.add(bill)
    db.commit()
    return _to_out(db, user.id, p)


@router.put("/email", response_model=dict)
def bind_email(body: ProfileEmailIn, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """绑定/修改邮箱（用于找回密码）。"""
    if body.email == user.email:
        return {"message": "邮箱未变化"}
    email_exists = db.execute(
        select(User).where(User.email == str(body.email), User.id != user.id)
    ).scalar_one_or_none()
    if email_exists:
        raise biz_error("EMAIL_TAKEN", "该邮箱已被其他账号绑定")
    user.email = str(body.email)
    db.commit()
    return {"message": "邮箱已更新"}

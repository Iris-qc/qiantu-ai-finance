"""系统内提醒：预算 / 异常消费 / 储蓄目标。"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..core import timeutil
from ..core.deps import clamp_page, get_current_user, get_db
from ..core.errors import not_found
from ..models import Notification, User
from ..schemas.notification import NotificationListOut, NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListOut)
def list_notifications(
    unread_only: bool = False,
    kind: str | None = None,
    page: int = 1,
    page_size: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, page_size = clamp_page(page, page_size)
    q = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    if kind:
        q = q.where(Notification.kind == kind)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    items = db.execute(
        q.order_by(Notification.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    unread = db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id, Notification.read_at.is_(None)
        )
    ).scalar_one()
    return NotificationListOut(
        items=[NotificationOut.model_validate(n) for n in items],
        unread_count=unread,
    )


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise not_found("提醒不存在")
    if n.read_at is None:
        n.read_at = timeutil.now()
        db.commit()
    return n


@router.post("/read-all", response_model=dict)
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=timeutil.now())
    )
    db.commit()
    return {"message": "已全部标记为已读"}

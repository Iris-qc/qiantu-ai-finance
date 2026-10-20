"""提醒服务：按 (user_id, dedup_key) 去重，条件持续满足只更新、条件解除即删除。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Notification


def upsert_notification(
    db: Session,
    user_id: int,
    *,
    kind: str,
    level: str,
    dedup_key: str,
    title: str,
    content: str,
    bill_id: int | None = None,
) -> Notification:
    n = db.execute(
        select(Notification).where(
            Notification.user_id == user_id, Notification.dedup_key == dedup_key
        )
    ).scalar_one_or_none()
    if n is None:
        n = Notification(
            user_id=user_id, kind=kind, level=level, dedup_key=dedup_key,
            title=title, content=content, bill_id=bill_id,
        )
        db.add(n)
    else:
        n.level = level
        n.title = title
        n.content = content
        n.bill_id = bill_id
        n.read_at = None  # 状态升级时重新变为未读
    db.flush()
    return n


def clear_notification(db: Session, user_id: int, dedup_key: str) -> None:
    n = db.execute(
        select(Notification).where(
            Notification.user_id == user_id, Notification.dedup_key == dedup_key
        )
    ).scalar_one_or_none()
    if n is not None:
        db.delete(n)

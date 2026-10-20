"""储蓄目标：设置 / 进度 / 建议储蓄额 / 风险提醒。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_db
from ..core.errors import not_found
from ..models import Goal, User
from ..schemas.goal import GoalIn, GoalListOut, GoalOut, GoalUpdateIn
from ..services import goals as goal_svc

router = APIRouter(prefix="/goals", tags=["goals"])


def _to_out(db: Session, g: Goal) -> GoalOut:
    m = goal_svc.goal_metrics(g, goal_svc.allowance_for(db, g.user_id))
    return GoalOut(
        id=g.id, name=g.name, target_cents=g.target_cents, current_cents=g.current_cents,
        deadline=g.deadline, note=g.note, created_at=g.created_at, **m,
    )


@router.get("", response_model=GoalListOut)
def list_goals(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Goal).where(Goal.user_id == user.id).order_by(Goal.deadline)
    ).scalars().all()
    return GoalListOut(items=[_to_out(db, g) for g in rows])


@router.post("", response_model=GoalOut, status_code=201)
def create_goal(body: GoalIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = Goal(user_id=user.id, name=body.name.strip(), target_cents=body.target_cents,
             current_cents=body.current_cents, deadline=body.deadline, note=body.note)
    db.add(g)
    db.flush()
    goal_svc.sync_goal_notification(db, g, goal_svc.goal_metrics(g, goal_svc.allowance_for(db, user.id)))
    db.commit()
    return _to_out(db, g)


@router.patch("/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, body: GoalUpdateIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    g = db.get(Goal, goal_id)
    if g is None or g.user_id != user.id:
        raise not_found("储蓄目标不存在")
    if body.name is not None:
        g.name = body.name.strip()
    if body.target_cents is not None:
        g.target_cents = body.target_cents
    if body.current_cents is not None:
        g.current_cents = body.current_cents
    if body.deadline is not None:
        g.deadline = body.deadline
    if body.note is not None:
        g.note = body.note
    db.flush()
    goal_svc.sync_goal_notification(db, g, goal_svc.goal_metrics(g, goal_svc.allowance_for(db, user.id)))
    db.commit()
    return _to_out(db, g)


@router.delete("/{goal_id}", status_code=204)
def delete_goal(goal_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = db.get(Goal, goal_id)
    if g is None or g.user_id != user.id:
        raise not_found("储蓄目标不存在")
    from ..services.notify import clear_notification
    clear_notification(db, user.id, f"goal:{g.id}")
    db.delete(g)
    db.commit()

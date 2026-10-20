"""分类管理：内置分类（共享、禁止删除）+ 用户自定义分类（软删除，历史账单保留名称快照）。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import timeutil
from ..core.deps import get_current_user, get_db
from ..core.errors import biz_error, forbidden, not_found
from ..models import Budget, Category, User
from ..schemas.category import CategoryIn, CategoryOut
from ..services.parsing import BUILTIN_EXPENSE, BUILTIN_INCOME

router = APIRouter(prefix="/categories", tags=["categories"])


def _builtins() -> list[Category]:
    return [Category(user_id=None, name=n, kind="expense", is_builtin=True) for n in BUILTIN_EXPENSE] + \
           [Category(user_id=None, name=n, kind="income", is_builtin=True) for n in BUILTIN_INCOME]


def ensure_builtins(db: Session) -> None:
    """幂等：内置分类缺失时补齐（空库启动兜底；正常由迁移/种子数据创建）。"""
    existing = set(db.execute(
        select(Category.name, Category.kind).where(Category.is_builtin.is_(True))
    ).all())
    for b in _builtins():
        if (b.name, b.kind) not in existing:
            db.add(b)
    db.flush()


@router.get("", response_model=list[CategoryOut])
def list_categories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Category).where(
            (Category.user_id == user.id) | (Category.user_id.is_(None)),
            Category.deleted_at.is_(None),
        ).order_by(Category.kind, Category.is_builtin.desc(), Category.id)
    ).scalars().all()
    return [
        CategoryOut(id=c.id, name=c.name, kind=c.kind, is_builtin=c.is_builtin) for c in rows
    ]


def _check_duplicate(db: Session, user_id: int, name: str, kind: str, exclude_id: int | None = None) -> None:
    q = select(Category).where(
        Category.kind == kind, Category.name == name, Category.deleted_at.is_(None),
    )
    if exclude_id is not None:
        q = q.where(Category.id != exclude_id)
    rows = db.execute(q).scalars().all()
    for c in rows:
        if c.user_id is None:
            raise biz_error("DUPLICATE_NAME", f"「{name}」与内置分类重名，请换个名称")
        if c.user_id == user_id:
            raise biz_error("DUPLICATE_NAME", f"已有同名分类「{name}」")


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryIn, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    _check_duplicate(db, user.id, body.name, body.kind)
    cat = Category(user_id=user.id, name=body.name, kind=body.kind, is_builtin=False)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return CategoryOut(id=cat.id, name=cat.name, kind=cat.kind, is_builtin=False)


def _get_owned(db: Session, user: User, category_id: int) -> Category:
    cat = db.get(Category, category_id)
    if cat is None or cat.deleted_at is not None:
        raise not_found("分类不存在")
    if cat.user_id is not None and cat.user_id != user.id:
        # 与其他用户资源隔离保持一致：返回 404，不暴露资源存在性
        raise not_found("分类不存在")
    return cat


@router.patch("/{category_id}", response_model=CategoryOut)
def rename_category(category_id: int, body: CategoryIn, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    cat = _get_owned(db, user, category_id)
    if cat.is_builtin:
        raise forbidden("系统内置分类不允许修改")
    _check_duplicate(db, user.id, body.name, body.kind, exclude_id=cat.id)
    old_name, old_kind = cat.name, cat.kind
    cat.name = body.name
    cat.kind = body.kind
    # 历史账单保留记录时的名称快照；仅同步该分类未删除预算的展示名称
    db.execute(
        Budget.__table__.update()
        .where(Budget.category_id == cat.id)
        .values(category_name=body.name)
    )
    db.commit()
    return CategoryOut(id=cat.id, name=cat.name, kind=cat.kind, is_builtin=False)


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    cat = _get_owned(db, user, category_id)
    if cat.is_builtin:
        raise forbidden("系统内置分类不允许删除")
    # 软删除：历史账单的 category_id 仍指向该行、category_name 快照保持不变，可正常显示原分类名称
    cat.deleted_at = timeutil.now()
    db.commit()

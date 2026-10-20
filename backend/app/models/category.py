from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class Category(Base):
    """消费/收入分类。

    - user_id 为空 = 系统内置分类（全体用户可见，禁止删除）。
    - 自定义分类按用户隔离；删除采用软删除（deleted_at）。
    - 账单保存分类名称快照（Bill.category_name），删除分类后历史账单仍显示原名称。
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(12), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # expense | income
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "uq_category_name_active",
            "user_id", "kind", "name",
            unique=True,
            postgresql_where=None,  # 内置分类 user_id 为 NULL，PG 唯一索引不拦截，改由服务层校验
        ),
    )

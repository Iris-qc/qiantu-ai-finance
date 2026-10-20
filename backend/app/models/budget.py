from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class Budget(Base):
    """预算：同一 (用户, 月份, 范围, 分类) 唯一，重复设置即覆盖更新。"""

    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    month_start: Mapped[date] = mapped_column(Date, nullable=False)  # 预算生效月份（取每月 1 日）
    scope: Mapped[str] = mapped_column(String(10), nullable=False)  # total | category
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    category_name: Mapped[str | None] = mapped_column(String(12))  # 分类预算的名称快照
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)  # > 0
    threshold_percent: Mapped[int] = mapped_column(Integer, default=80, nullable=False)  # 50-100
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("uq_budget_scope", "user_id", "month_start", "scope", "category_id", unique=True),
    )

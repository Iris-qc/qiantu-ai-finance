from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class Bill(Base):
    """账单。

    - bill_type: income | expense | adjustment（资产校准）。
      income/expense 的 amount_cents 恒为正；adjustment 存校准差额（可正可负）。
    - category_name 为分类名称快照；category_id 指向分类（分类被删后置空）。
    - 所有金额为整数分。
    """

    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    bill_type: Mapped[str] = mapped_column(String(12), nullable=False)  # income|expense|adjustment
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    category_name: Mapped[str] = mapped_column(String(12), nullable=False)  # 分类名称快照
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    note: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(10), default="manual", nullable=False)  # manual|nlp|voice|ocr
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_bills_user_occurred", "user_id", "occurred_at"),
    )

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class Notification(Base):
    """系统内提醒（预算提醒 / 异常消费提醒 / 储蓄目标提醒）。

    防刷屏机制：同一 (user_id, dedup_key) 只有一条记录，条件持续满足时只更新内容、
    不新增；条件解除（如消费回落到阈值以下）时删除记录，避免反复产生大量重复通知。
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(12), nullable=False)  # budget | anomaly | goal
    level: Mapped[str] = mapped_column(String(10), nullable=False)  # info | warning | danger
    dedup_key: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(60), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    bill_id: Mapped[int | None] = mapped_column(
        ForeignKey("bills.id", ondelete="SET NULL"), nullable=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("uq_notification_dedup", "user_id", "dedup_key", unique=True),
    )

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.session import Base


class Profile(Base):
    """用户财务档案。

    - initial_assets_cents：首次录入的可支配资产（资产基数），初始化后不可直接修改，只能通过"资产校准"调整。
    - 当前资产不落库，每次按 `初始资产 + Σ收入 - Σ支出 + Σ校准差额` 全量重算，保证增删改后一致。
    - 生活费发放日只用于周期计算，发放日不会自动增加资产；实际到账由用户记录收入账单。
    """

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    initialized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    initial_assets_cents: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    allowance_cents: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    allowance_day: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1-31
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="profile")

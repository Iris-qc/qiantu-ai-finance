from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class Report(Base):
    """消费报告（月度 / 学期 / 年度）。content 为结构化报告正文；pdf 按需生成并缓存路径。"""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    report_type: Mapped[str] = mapped_column(String(10), nullable=False)  # monthly|semester|annual
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(Text)  # 相对导出目录的文件名
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

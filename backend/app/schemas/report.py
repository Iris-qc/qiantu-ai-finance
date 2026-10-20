"""消费报告 schema。"""
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class ReportGenerateIn(BaseModel):
    report_type: str = Field(pattern="^(monthly|semester|annual)$")
    period_start: str | None = Field(default=None, description="YYYY-MM-DD；monthly 可给 YYYY-MM")
    period_end: str | None = None

    @model_validator(mode="after")
    def check_period(self):
        # monthly：允许只给 period_start 形如 YYYY-MM（取整月），或给完整起止
        return self


class ReportOut(BaseModel):
    id: int
    report_type: str
    period_start: date
    period_end: date
    title: str
    content: dict
    has_pdf: bool
    created_at: datetime


class ReportListOut(BaseModel):
    items: list[ReportOut]


class ReportPeriodsOut(BaseModel):
    """当前可选的报告周期（前端下拉）。"""
    monthly: list[str]      # 最近 12 个月 "YYYY-MM"
    semesters: list[dict]   # [{label, start, end}] 最近 4 个学期
    years: list[str]        # 最近 5 年

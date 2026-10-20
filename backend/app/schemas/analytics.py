"""消费分析 schema。"""
from pydantic import BaseModel


class TrendPoint(BaseModel):
    label: str          # 日期 "MM-DD" / 周 "YYYY-Wxx" / 月 "YYYY-MM"
    expense_cents: int
    income_cents: int


class CategoryShare(BaseModel):
    category_name: str
    amount_cents: int
    percent: float  # 仅展示用


class SummaryOut(BaseModel):
    period_start: str
    period_end: str
    expense_cents: int
    income_cents: int
    bill_count: int
    top_category: str | None
    prev_expense_cents: int | None   # 上一同长周期的支出（用于环比）
    prev_income_cents: int | None


class TrendOut(BaseModel):
    granularity: str  # day | week | month
    points: list[TrendPoint]


class CategoryOut(BaseModel):
    items: list[CategoryShare]
    total_cents: int

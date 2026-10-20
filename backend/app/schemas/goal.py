"""储蓄目标 schema。"""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    target_cents: int = Field(gt=0)
    current_cents: int = Field(default=0, ge=0)
    deadline: date
    note: str | None = Field(default=None, max_length=200)


class GoalUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    target_cents: int | None = Field(default=None, gt=0)
    current_cents: int | None = Field(default=None, ge=0)
    deadline: date | None = None
    note: str | None = Field(default=None, max_length=200)


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    target_cents: int
    current_cents: int
    deadline: date
    note: str | None
    created_at: object
    # —— 派生指标 ——
    progress_percent: int
    remaining_cents: int
    days_left: int
    suggested_daily_cents: int
    suggested_monthly_cents: int
    risk: str  # on_track | tight | overdue | done


class GoalListOut(BaseModel):
    items: list[GoalOut]

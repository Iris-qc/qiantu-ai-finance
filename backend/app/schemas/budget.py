"""预算 schema。"""
from pydantic import BaseModel, Field, model_validator


class BudgetUpsertIn(BaseModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="预算月份 YYYY-MM")
    scope: str = Field(pattern="^(total|category)$")
    category_id: int | None = Field(default=None, description="分类预算必填；总预算留空")
    amount_cents: int = Field(gt=0, description="预算金额（分），大于 0")
    threshold_percent: int = Field(default=80, ge=50, le=100, description="预警阈值 50-100%")

    @model_validator(mode="after")
    def check_scope(self):
        if self.scope == "category" and self.category_id is None:
            raise ValueError("分类预算必须指定 category_id")
        if self.scope == "total":
            self.category_id = None
        return self


class BudgetItemOut(BaseModel):
    id: int
    scope: str
    category_id: int | None
    category_name: str | None
    amount_cents: int
    spent_cents: int
    usage_percent: int  # 四舍五入取整
    threshold_percent: int
    status: str  # normal | approaching | exceeded


class BudgetForecastOut(BaseModel):
    days_total: int
    days_elapsed: int
    days_remaining: int
    avg_daily_cents: int
    spent_cents: int
    predicted_cents: int
    budget_cents: int | None  # 总预算；未设置时为 None
    risk: str  # none | potential | high | no_budget
    risk_label: str


class BudgetOverviewOut(BaseModel):
    month: str
    items: list[BudgetItemOut]
    forecast: BudgetForecastOut

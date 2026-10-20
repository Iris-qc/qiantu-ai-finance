"""用户财务档案 schema。金额一律为整数分（元 × 100）。"""
from datetime import date

from pydantic import BaseModel, EmailStr, Field


class ProfileInitIn(BaseModel):
    """首次初始化：录入可支配资产基数、每月生活费、发放日。"""
    initial_assets_cents: int = Field(ge=0, description="当前可支配资产（分）")
    allowance_cents: int = Field(ge=0, description="每月生活费金额（分）")
    allowance_day: int = Field(ge=1, le=31, description="生活费每月发放日（1-31）")


class ProfileUpdateIn(BaseModel):
    allowance_cents: int = Field(ge=0)
    allowance_day: int = Field(ge=1, le=31)


class ProfileEmailIn(BaseModel):
    email: EmailStr


class CalibrateIn(BaseModel):
    actual_assets_cents: int = Field(ge=0, description="用户实际手持资产（分）")


class ProfileOut(BaseModel):
    initialized: bool
    initial_assets_cents: int
    allowance_cents: int
    allowance_day: int
    current_assets_cents: int
    total_income_cents: int
    total_expense_cents: int
    adjustment_cents: int
    days_to_next_allowance: int
    next_allowance_date: date
    suggested_daily_cents: int

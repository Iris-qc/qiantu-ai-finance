"""账单 schema。金额一律为整数分。occurred_at 为业务时区 ISO8601。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BillIn(BaseModel):
    bill_type: str = Field(pattern="^(income|expense)$", description="收入/支出（资产校准走独立接口）")
    amount_cents: int = Field(gt=0, description="金额（分），必须大于 0")
    category_id: int = Field(description="分类 ID（收入/支出必填）")
    occurred_at: datetime | None = None  # 可选，默认系统当前时间
    note: str | None = Field(default=None, max_length=200)

    @field_validator("note")
    @classmethod
    def strip_note(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
        return v or None


class BillUpdateIn(BaseModel):
    bill_type: str | None = Field(default=None, pattern="^(income|expense)$")
    amount_cents: int | None = Field(default=None, gt=0)
    category_id: int | None = None
    occurred_at: datetime | None = None
    note: str | None = Field(default=None, max_length=200)

    @field_validator("note")
    @classmethod
    def strip_note(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
        return v or None

    @model_validator(mode="after")
    def at_least_one(self):
        if all(v is None for v in (self.bill_type, self.amount_cents, self.category_id,
                                   self.occurred_at, self.note)):
            raise ValueError("至少提供一个要修改的字段")
        return self


class BillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bill_type: str
    amount_cents: int
    category_id: int | None
    category_name: str
    occurred_at: datetime
    note: str | None
    source: str
    created_at: datetime
    updated_at: datetime


class BillListOut(BaseModel):
    items: list[BillOut]
    total: int
    page: int
    page_size: int

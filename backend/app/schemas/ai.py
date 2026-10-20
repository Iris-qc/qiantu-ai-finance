"""AI 智能记账 / 财务助手 schema。"""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class DraftItem(BaseModel):
    """账单草稿：解析结果，未经用户确认不得入库。"""
    bill_type: str = Field(pattern="^(income|expense)$", default="expense")
    amount_cents: int = Field(gt=0, description="金额（分）")
    category_id: int | None = None
    category_name: str = Field(min_length=1, max_length=12)
    occurred_at: datetime | None = None
    note: str | None = Field(default=None, max_length=200)
    merchant: str | None = Field(default=None, max_length=50, description="识别出的商家（可并入备注）")


class NlParseIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)

    @field_validator("text")
    @classmethod
    def strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("请输入要记账的内容")
        return v


class NlParseOut(BaseModel):
    mode: str  # demo | external
    notice: str
    items: list[DraftItem]


class SpeechParseOut(BaseModel):
    mode: str
    transcript: str
    items: list[DraftItem]
    notice: str


class OcrParseOut(BaseModel):
    mode: str
    ocr_text: str
    items: list[DraftItem]
    notice: str


class DraftConfirmIn(BaseModel):
    source: str = Field(pattern="^(nlp|voice|ocr)$")
    items: list[DraftItem] = Field(min_length=1, max_length=50)


class DraftConfirmOut(BaseModel):
    created: list[int]  # 新建账单 ID 列表


class AdviceIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class AdviceBasis(BaseModel):
    label: str
    value: str


class AdviceOut(BaseModel):
    mode: str  # demo | external
    answer: str
    basis: list[AdviceBasis]
    warnings: list[str]
    disclaimer: str

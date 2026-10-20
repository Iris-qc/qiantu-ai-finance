"""分类 schema。"""
from pydantic import BaseModel, Field, field_validator


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=12)
    kind: str = Field(pattern="^(expense|income)$")

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("分类名称不能为空")
        return v


class CategoryOut(BaseModel):
    id: int
    name: str
    kind: str
    is_builtin: bool

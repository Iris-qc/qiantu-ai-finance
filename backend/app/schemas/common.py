"""公共 schema：统一错误格式 {code, message, fields?}。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApiError(BaseModel):
    code: str
    message: str
    fields: dict | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None = None
    created_at: datetime


class Page(BaseModel):
    total: int
    page: int
    page_size: int

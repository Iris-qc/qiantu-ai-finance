"""认证相关 schema。"""
import re

from pydantic import BaseModel, EmailStr, Field, field_validator

USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{4,12}$")
PASSWORD_RE = re.compile(r"^[A-Za-z0-9_!@#$%^*()+.-]{8,20}$")


class RegisterIn(BaseModel):
    username: str = Field(description="唯一用户名，4-12 位字母/数字/下划线/连字符，注册后不可修改")
    password: str = Field(description="8-20 位，需同时包含字母和数字")
    email: EmailStr | None = None

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        if not USERNAME_RE.match(v):
            raise ValueError("用户名需为 4-12 位字母、数字、下划线或连字符")
        return v

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if not PASSWORD_RE.match(v):
            raise ValueError("密码需为 8-20 位，仅限字母、数字及 _!@#$%^*()+.-")
        if not re.search(r"[A-Za-z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("密码需同时包含字母和数字")
        return v


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class ResetRequestIn(BaseModel):
    email: EmailStr


class ResetConfirmIn(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$", description="6 位数字验证码")
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if not PASSWORD_RE.match(v):
            raise ValueError("密码需为 8-20 位，仅限字母、数字及 _!@#$%^*()+.-")
        if not re.search(r"[A-Za-z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("密码需同时包含字母和数字")
        return v


from .common import UserOut  # noqa: E402

TokenOut.model_rebuild()

"""金额工具：全系统金额以"整数分"为单位（BIGINT 存储、API 传输），禁止浮点参与金额计算。

字符串 → 分：只做字符串解析（yuan_str 必须形如 "12" 或 "12.34"，最多两位小数）。
分 → 字符串：两位小数固定输出，用于展示/序列化。
"""
import re

_YUAN_RE = re.compile(r"^(\d{1,12})(?:\.(\d{1,2}))?$")


def yuan_to_cents(value: str | int | float) -> int:
    """把元（字符串形式最安全）转成整数分。例：'12.34' -> 1234。"""
    if isinstance(value, int):
        return value * 100
    if isinstance(value, float):
        raise ValueError("金额请使用字符串，避免浮点误差")
    s = value.strip()
    m = _YUAN_RE.match(s)
    if not m:
        raise ValueError(f"金额格式不正确: {value!r}（应为数字，最多两位小数）")
    yuan, frac = m.group(1), (m.group(2) or "").ljust(2, "0")
    return int(yuan) * 100 + int(frac)


def cents_to_yuan(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    c = abs(cents)
    return f"{sign}{c // 100}.{c % 100:02d}"


def cents_to_yuan_float(cents: int) -> float:
    """仅用于图表展示（Recharts 需要数值），不用于业务计算。"""
    return cents / 100.0

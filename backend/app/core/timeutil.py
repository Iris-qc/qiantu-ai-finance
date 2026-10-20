"""时间工具：业务时区（默认 Asia/Shanghai）与 UTC 存储之间的转换。"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .config import get_settings


def app_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().app_tz)


def now() -> datetime:
    """业务时区当前时间（带 tzinfo）。"""
    return datetime.now(app_tz())


def as_app_tz(dt: datetime) -> datetime:
    """把任意 aware/naive datetime 转成业务时区 aware。naive 视为业务时区。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=app_tz())
    return dt.astimezone(app_tz())


def local_date(dt: datetime) -> date:
    return as_app_tz(dt).date()


def month_start(d: date | datetime) -> datetime:
    """该日期所在月第一天 00:00（业务时区 aware）。"""
    if isinstance(d, datetime):
        d = local_date(d)
    return datetime(d.year, d.month, 1, tzinfo=app_tz())


def next_month_start(d: date | datetime) -> datetime:
    ms = month_start(d)
    return datetime(ms.year + (ms.month // 12), ms.month % 12 + 1, 1, tzinfo=app_tz())


def month_days(d: date) -> int:
    nxt = next_month_start(d)
    return (nxt.astimezone(app_tz()).date() - month_start(d).astimezone(app_tz()).date()).days


def parse_date(s: str) -> date:
    """严格解析 YYYY-MM-DD。"""
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("日期格式应为 YYYY-MM-DD")


def next_allowance_date(pay_day: int, today: date) -> date:
    """距今天最近的下一个发放日（含今天）。pay_day 超过当月天数时取当月最后一天。"""
    year, month = today.year, today.month
    first = date(year, month, 1)
    last = first + timedelta(days=month_days(first) - 1)
    day = min(pay_day, last.day)
    candidate = date(year, month, day)
    if candidate < today:
        first = date(year + (month // 12), month % 12 + 1, 1)
        last = first + timedelta(days=month_days(first) - 1)
        candidate = date(year + (month // 12), month % 12 + 1, min(pay_day, last.day))
    return candidate


def days_to_next_allowance(pay_day: int, today: date) -> int:
    return (next_allowance_date(pay_day, today) - today).days


def days_between(a: date, b: date) -> int:
    return (b - a).days

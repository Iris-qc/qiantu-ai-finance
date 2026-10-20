"""自然语言记账解析。

- 未配置外部 AI（或 ai_mode=demo）时使用本地规则解析器（演示模式），
  返回结果会明确标注"演示模式解析（本地规则，未调用外部 AI）"。
- 配置外部 AI 时调用 OpenAI 兼容接口，由 LLM 输出结构化草稿。
- 解析结果一律是草稿，只有用户确认后才写入正式账单。
"""
import json
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.timeutil import app_tz, now
from ..models import Category
from .providers import llm

BUILTIN_EXPENSE = ["餐饮", "交通", "学习", "娱乐", "网购", "生活用品", "其他"]
BUILTIN_INCOME = ["生活费", "兼职", "奖学金", "红包", "其他收入"]

# 关键词 → 分类（顺序即优先级）
_EXPENSE_KEYWORDS: list[tuple[str, str]] = [
    ("餐饮", "奶茶 咖啡 早餐 午餐 午饭 晚餐 晚饭 夜宵 食堂 外卖 饭 面 米粉 烧烤 火锅 麻辣烫 水果 零食 饮料 麦当劳 肯德基 汉堡 披萨 蛋糕 面包"),
    ("交通", "打车 滴滴 出租车 地铁 公交 高铁 火车 机票 共享单车 骑行 加油 停车 大巴 船票"),
    ("学习", "书 教材 课本 文具 学费 培训 课程 打印 复印 考试 报名 网课 笔 本子 资料 论文"),
    ("娱乐", "电影 游戏 唱歌 KTV 剧本杀 演唱会 演出 会员 视频 桌游 网吧 电玩 门票 旅游 景区"),
    ("网购", "淘宝 京东 拼多多 天猫 网购 快递 衣服 鞋 裤子 裙子 化妆品 护肤品 数码 耳机 手机壳 键盘 鼠标 背包 帽子 围巾"),
    ("生活用品", "洗发水 牙膏 牙刷 纸巾 洗衣液 沐浴露 日用品 生活用品 毛巾 水杯 垃圾袋 蚊香"),
]
_INCOME_KEYWORDS: list[tuple[str, str]] = [
    ("生活费", "生活费 家里转 家里给 爸妈给 生活费到账"),
    ("兼职", "兼职 打工 实习工资 家教 发传单 助管 勤工俭学"),
    ("奖学金", "奖学金 助学金 补贴 竞赛奖金"),
    ("红包", "红包 压岁钱 生日红包"),
    ("其他收入", "退款 报销 卖二手 利息 转账 收入 赚了"),
]

_AMOUNT_RE = re.compile(r"(\d+(?:\.\d{1,2})?)\s*(?:元|块|块钱)?")
_TIME_WORDS = {"今天": 0, "昨天": 1, "前天": 2, "大前天": 3}
_DATE_RE = re.compile(r"(\d{1,2})月(\d{1,2})[日号]")
_HOUR_HINTS = {"早上": 8, "上午": 10, "中午": 12, "下午": 15, "晚上": 19, "凌晨": 1}


class ParseFailure(Exception):
    """无法解析出任何有效消费信息。"""
    pass


def _match_category(text: str, is_income: bool) -> str:
    table = _INCOME_KEYWORDS if is_income else _EXPENSE_KEYWORDS
    for cat, words in table:
        for w in words.split():
            if w in text:
                return cat
    return "其他收入" if is_income else "其他"


def _parse_amount(text: str) -> int | None:
    """取文本中第一个金额（数字+可选单位），严格字符串解析为分。"""
    for m in _AMOUNT_RE.finditer(text):
        try:
            from ..core.money import yuan_to_cents
            return yuan_to_cents(m.group(1))
        except ValueError:
            continue
    return None


def _parse_occurred(text: str) -> datetime:
    """解析时间表达：今天/昨天/…、X月X日；默认当前时间。"""
    base = now()
    for word, days in _TIME_WORDS.items():
        if word in text:
            d = base.date() - timedelta(days=days)
            return datetime(d.year, d.month, d.day, 12, 0, tzinfo=app_tz())
    m = _DATE_RE.search(text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = base.year if (month, day) <= (base.month, base.day) or month >= base.month else base.year
        # 简化：若解析出的日期在未来 8 天内视为今年，否则视为去年；此处按当月逻辑取今年
        try:
            return datetime(base.year, month, day, 12, 0, tzinfo=app_tz())
        except ValueError:
            return base
    for hint, hour in _HOUR_HINTS.items():
        if hint in text:
            return base.replace(hour=hour, minute=0, second=0, microsecond=0)
    return base


def parse_nl_demo(text: str) -> list[dict]:
    """演示模式本地规则解析。返回草稿字典列表；无有效条目抛 ParseFailure。"""
    clauses = [c.strip() for c in re.split(r"[，,。；;、\n]|(?:\s+和\s+)", text) if c.strip()]
    items: list[dict] = []
    unparsed: list[str] = []
    for clause in clauses:
        amount = _parse_amount(clause)
        if amount is None or amount <= 0:
            unparsed.append(clause)
            continue
        is_income = any(w in clause for _, words in _INCOME_KEYWORDS for w in words.split())
        category = _match_category(clause, is_income)
        occurred = _parse_occurred(clause)
        items.append({
            "bill_type": "income" if is_income else "expense",
            "amount_cents": amount,
            "category_id": None,
            "category_name": category,
            "occurred_at": occurred,
            "note": clause,
            "merchant": None,
        })
    if not items:
        raise ParseFailure("未能识别出消费信息，请重新描述（例如：今天奶茶18，打车25）或手动录入")
    return items, unparsed


_EXTERNAL_PROMPT = """你是记账助手。从用户输入的中文自然语言中提取多条收入/支出记录，输出 JSON 数组（不要输出其他内容）。
每条记录字段：bill_type（"income"或"expense"）、amount（元，数字，最多两位小数）、category（分类名，从给定分类中选择最接近的：
{expense_cats}（支出）或 {income_cats}（收入））、date（"YYYY-MM-DD"或 null 表示今天）、note（简要说明，可空）、merchant（商家，可空）。
没有可提取的消费时输出空数组 []。用户输入：{text}"""


def parse_nl_external(text: str, user_categories: list[Category]) -> tuple[list[dict], str]:
    s = get_settings()
    expense_cats = "、".join(c.name for c in user_categories if c.kind == "expense") or "、".join(BUILTIN_EXPENSE)
    income_cats = "、".join(c.name for c in user_categories if c.kind == "income") or "、".join(BUILTIN_INCOME)
    prompt = _EXTERNAL_PROMPT.format(expense_cats=expense_cats, income_cats=income_cats, text=text)
    content = llm.chat_json(
        s.ai_api_base_url, s.ai_api_key, s.ai_model,
        system="你是一个严谨的中文记账解析助手，只输出 JSON。", user=prompt,
        timeout=s.ai_timeout_seconds,
    )
    try:
        data = json.loads(content) if isinstance(content, str) else content
        if not isinstance(data, list):
            raise ValueError("bad shape")
    except (ValueError, json.JSONDecodeError) as e:
        raise ParseFailure("外部 AI 返回结果无法解析，请重试或改用手动记账") from e

    cat_by_name = {c.name: c for c in user_categories}
    items = []
    for row in data[:20]:
        amount = None
        try:
            from ..core.money import yuan_to_cents
            amount = yuan_to_cents(str(row.get("amount", "")))
        except ValueError:
            continue
        if amount is None or amount <= 0:
            continue
        bill_type = "income" if str(row.get("bill_type", "")).lower() == "income" else "expense"
        cat_name = str(row.get("category") or "")
        cat = cat_by_name.get(cat_name)
        if cat is None:
            cat_name = "其他收入" if bill_type == "income" else "其他"
        elif cat.kind != bill_type:
            cat_name = "其他收入" if bill_type == "income" else "其他"
            cat = None
        date_str = str(row.get("date") or "")
        occurred = now()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            try:
                occurred = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=12, tzinfo=app_tz())
            except ValueError:
                pass
        note = str(row.get("note") or "")[:200] or None
        merchant = str(row.get("merchant") or "")[:50] or None
        items.append({
            "bill_type": bill_type, "amount_cents": amount,
            "category_id": cat.id if cat else None, "category_name": cat_name,
            "occurred_at": occurred, "note": note, "merchant": merchant,
        })
    if not items:
        raise ParseFailure("未能识别出消费信息，请重新描述（例如：今天奶茶18，打车25）或手动录入")
    return items, []


def parse_nl(db: Session, user_id: int, text: str) -> tuple[str, str, list[dict]]:
    """返回 (mode, notice, items)。"""
    s = get_settings()
    user_categories = db.execute(
        select(Category).where(
            (Category.user_id == user_id) | (Category.user_id.is_(None)),
            Category.deleted_at.is_(None),
        )
    ).scalars().all()
    use_external = s.ai_mode == "external" or (s.ai_mode == "auto" and s.has_llm)
    if use_external:
        try:
            items, _ = parse_nl_external(text, user_categories)
            return "external", "已调用外部 AI 解析（结果仍需你确认后保存）", items
        except Exception as e:  # 外部失败回退演示模式并如实说明
            demo_items, unparsed = parse_nl_demo(text)
            notice = (f"外部 AI 解析失败（{type(e).__name__}），已回退演示模式本地规则解析。"
                      + (f"未识别片段：{'；'.join(unparsed)}。" if unparsed else ""))
            return "demo", notice, demo_items
    items, unparsed = parse_nl_demo(text)
    notice = "演示模式解析（本地规则，未调用外部 AI）" + (f"；未识别片段：{'；'.join(unparsed)}" if unparsed else "")
    return "demo", notice, items

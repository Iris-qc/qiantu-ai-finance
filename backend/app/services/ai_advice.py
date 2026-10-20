"""AI 财务助手：只引用系统中真实存在的用户数据，缺数据时明确说明，绝不编造。

- 本地规则引擎（演示模式）：基于资产/预算/历史消费/生活费天数/储蓄目标做真实计算。
- 配置外部 AI 时调用 LLM 生成回答，同样仅注入真实上下文；调用失败回退本地引擎并如实说明。
"""
import json
import re
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.money import cents_to_yuan, yuan_to_cents
from ..core.timeutil import days_to_next_allowance, now
from ..models import Bill, Goal, Notification, Profile
from . import budgets as budget_svc
from .providers import llm

DISCLAIMER = "以上建议仅供理财参考，不构成任何承诺；系统不会据此修改你的账单、预算或资产数据。"


def _sum_expense_between(db: Session, user_id: int, start, end) -> int:
    return int(db.execute(
        select(func.coalesce(func.sum(Bill.amount_cents), 0)).where(
            Bill.user_id == user_id, Bill.bill_type == "expense",
            Bill.occurred_at >= start, Bill.occurred_at < end,
        )
    ).scalar_one())


def build_context(db: Session, user_id: int) -> dict:
    """汇集用户真实财务上下文。"""
    today = now().date()
    profile = db.execute(select(Profile).where(Profile.user_id == user_id)).scalar_one_or_none()
    from .assets import current_assets
    assets = current_assets(db, user_id) if profile and profile.initialized else None

    month = today.replace(day=1)
    nxt = (month + timedelta(days=32)).replace(day=1)
    spent_month = _sum_expense_between(db, user_id, month, nxt)
    recent_start = today - timedelta(days=30)
    spent_30 = _sum_expense_between(db, user_id, recent_start, today + timedelta(days=1))

    cat_rows = db.execute(
        select(Bill.category_name, func.sum(Bill.amount_cents))
        .where(Bill.user_id == user_id, Bill.bill_type == "expense",
               Bill.occurred_at >= month, Bill.occurred_at < nxt)
        .group_by(Bill.category_name).order_by(func.sum(Bill.amount_cents).desc())
    ).all()

    goals = db.execute(
        select(Goal).where(Goal.user_id == user_id).order_by(Goal.deadline)
    ).scalars().all()
    goal_info = []
    for g in goals:
        progress = int(round(g.current_cents * 100 / g.target_cents)) if g.target_cents else 0
        goal_info.append({
            "name": g.name, "target": g.target_cents, "current": g.current_cents,
            "deadline": g.deadline.isoformat(), "progress_percent": progress,
            "remaining": max(0, g.target_cents - g.current_cents),
            "days_left": (g.deadline - today).days,
        })

    unread_anomalies = int(db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id, Notification.kind == "anomaly",
            Notification.read_at.is_(None),
        )
    ).scalar_one())

    b = budget_svc.overview(db, user_id, month)
    return {
        "initialized": bool(profile and profile.initialized),
        "assets": assets,
        "allowance_cents": profile.allowance_cents if profile else 0,
        "days_to_allowance": days_to_next_allowance(profile.allowance_day, today) if profile else None,
        "spent_month": spent_month,
        "spent_30d": spent_30,
        "avg_daily_30d": spent_30 // 30,
        "month_categories": [{"name": n, "amount": int(a)} for n, a in cat_rows],
        "budget": b,
        "goals": goal_info,
        "unread_anomalies": unread_anomalies,
        "today": today.isoformat(),
    }


def _basis_items(ctx: dict) -> list[dict]:
    items = []
    if ctx["initialized"]:
        items.append({"label": "当前资产", "value": f"{cents_to_yuan(ctx['assets'])} 元"})
        items.append({"label": "距下次生活费", "value": f"{ctx['days_to_allowance']} 天"})
        if ctx["days_to_allowance"] and ctx["days_to_allowance"] > 0:
            daily = ctx["assets"] // ctx["days_to_allowance"]
            items.append({"label": "每日可支配上限", "value": f"约 {cents_to_yuan(daily)} 元"})
    else:
        items.append({"label": "资产数据", "value": "未完成财务初始化"})
    items.append({"label": "本月已支出", "value": f"{cents_to_yuan(ctx['spent_month'])} 元"})
    items.append({"label": "近30天日均支出", "value": f"约 {cents_to_yuan(ctx['avg_daily_30d'])} 元"})
    fb = ctx["budget"]["forecast"]
    if fb["budget_cents"] is not None:
        items.append({"label": "本月总预算", "value": f"{cents_to_yuan(fb['budget_cents'])} 元（已用 {fb['spent_cents'] * 100 // fb['budget_cents']}%）"})
        items.append({"label": "月底预测", "value": f"约 {cents_to_yuan(fb['predicted_cents'])} 元（{fb['risk_label']}）"})
    else:
        items.append({"label": "本月总预算", "value": "未设置"})
    if ctx["month_categories"]:
        top = ctx["month_categories"][0]
        items.append({"label": "本月最大支出类别", "value": f"{top['name']} {cents_to_yuan(top['amount'])} 元"})
    if ctx["goals"]:
        g = ctx["goals"][0]
        items.append({"label": "储蓄目标", "value": f"「{g['name']}」完成 {g['progress_percent']}%，还剩 {g['days_left']} 天"})
    else:
        items.append({"label": "储蓄目标", "value": "未设置"})
    if ctx["unread_anomalies"]:
        items.append({"label": "未读异常提醒", "value": f"{ctx['unread_anomalies']} 条"})
    return items


def _warnings(ctx: dict) -> list[str]:
    w = []
    fb = ctx["budget"]["forecast"]
    if fb["risk"] in ("potential", "high"):
        w.append(f"按当前消费速度，月底预测支出约 {cents_to_yuan(fb['predicted_cents'])} 元，"
                 f"存在{fb['risk_label']}，建议控制消费节奏。")
    if ctx["unread_anomalies"]:
        w.append(f"你有 {ctx['unread_anomalies']} 条未读异常消费提醒，建议先核对相关账单。")
    for g in ctx["goals"]:
        if 0 < g["days_left"] <= 14 and g["progress_percent"] < 60:
            w.append(f"储蓄目标「{g['name']}」距截止仅 {g['days_left']} 天、完成度 {g['progress_percent']}%，"
                     f"达成存在难度。")
    return w


def _answer_with_amount(ctx: dict, amount_cents: int, question: str) -> tuple[str, list[dict], list[str]]:
    basis = _basis_items(ctx)
    warnings = _warnings(ctx)
    if not ctx["initialized"]:
        return ("你还没有完成财务初始化（未录入当前资产），缺少判断这笔消费的依据。"
                "请先在「账户设置」中录入资产、生活费和发放日后再问我。"), basis, warnings

    assets = ctx["assets"]
    y = cents_to_yuan(amount_cents)
    remaining_after = assets - amount_cents
    fb = ctx["budget"]["forecast"]
    month_remaining = None
    if fb["budget_cents"] is not None:
        month_remaining = fb["budget_cents"] - fb["spent_cents"]
    days = ctx["days_to_allowance"] or 1

    lines = []
    if remaining_after >= 0:
        lines.append(f"从账本数据看，这笔 {y} 元的消费在当前资产（{cents_to_yuan(assets)} 元）范围内，"
                     f"支付后剩余约 {cents_to_yuan(remaining_after)} 元。")
    else:
        lines.append(f"当前资产 {cents_to_yuan(assets)} 元不足以覆盖这笔 {y} 元的消费"
                     f"（缺口 {cents_to_yuan(-remaining_after)} 元），不建议现在购买。")
    if month_remaining is not None:
        if amount_cents <= month_remaining:
            lines.append(f"本月总预算剩余 {cents_to_yuan(month_remaining)} 元，这笔消费在剩余预算内。")
        else:
            lines.append(f"本月总预算已用 {fb['spent_cents'] * 100 // fb['budget_cents']}%，"
                         f"剩余 {cents_to_yuan(max(month_remaining, 0))} 元，这笔消费会超出本月预算，建议谨慎。")
    after_daily = remaining_after // days if remaining_after > 0 else 0
    if after_daily > 0:
        lines.append(f"支付后到下次生活费发放（{days} 天）前，每日可支配约 {cents_to_yuan(after_daily)} 元；"
                     f"你近 30 天日均支出约 {cents_to_yuan(ctx['avg_daily_30d'])} 元，"
                     + ("基本匹配，可以接受。" if after_daily >= ctx["avg_daily_30d"] * 0.7
                        else "低于你的日常消费水平，之后需要适当收紧。"))
    for g in ctx["goals"]:
        if g["days_left"] > 0 and g["progress_percent"] < 100:
            need_daily = g["remaining"] // g["days_left"]
            if need_daily > 0:
                lines.append(f"注意：储蓄目标「{g['name']}」还需每天存约 {cents_to_yuan(need_daily)} 元，"
                             f"这笔消费会影响目标进度。")
    verdict = "综上，这笔消费可以接受，但请量入为出。" if remaining_after >= 0 and (
        month_remaining is None or amount_cents <= month_remaining) else "综上，建议暂缓这笔消费或寻找更便宜的替代。"
    return ("\n".join(lines) + "\n" + verdict), basis, warnings


def _answer_general(ctx: dict, question: str) -> tuple[str, list[dict], list[str]]:
    basis = _basis_items(ctx)
    warnings = _warnings(ctx)
    if not ctx["initialized"]:
        return ("你还没有完成财务初始化（未录入当前资产），我只能基于已有账单给出有限信息。"
                "请先在「账户设置」中完成初始化，我才能给出完整的消费建议。"), basis, warnings
    lines = []
    fb = ctx["budget"]["forecast"]
    lines.append(f"你本月已支出 {cents_to_yuan(ctx['spent_month'])} 元，"
                 f"近 30 天日均支出约 {cents_to_yuan(ctx['avg_daily_30d'])} 元。")
    if fb["budget_cents"] is not None:
        lines.append(f"本月总预算 {cents_to_yuan(fb['budget_cents'])} 元，已使用 "
                     f"{fb['spent_cents'] * 100 // fb['budget_cents']}%；按当前速度月底预计支出 "
                     f"约 {cents_to_yuan(fb['predicted_cents'])} 元（{fb['risk_label']}）。")
    else:
        lines.append("你还没有设置本月总预算，建议在「预算」页设置，便于控制月底风险。")
    if ctx["month_categories"]:
        lines.append("本月支出主要集中在：" + "、".join(
            f"{c['name']} {cents_to_yuan(c['amount'])} 元" for c in ctx["month_categories"][:3]) + "。")
    if ctx["days_to_allowance"] is not None and ctx["days_to_allowance"] > 0:
        daily = ctx["assets"] // ctx["days_to_allowance"]
        lines.append(f"距下次生活费还有 {ctx['days_to_allowance']} 天，按当前资产折算每日可支配约 "
                     f"{cents_to_yuan(daily)} 元，可作为消费上限参考。")
    if ctx["goals"]:
        for g in ctx["goals"]:
            if g["days_left"] > 0 and g["progress_percent"] < 100:
                lines.append(f"储蓄目标「{g['name']}」完成 {g['progress_percent']}%，"
                             f"剩余 {g['days_left']} 天，每天需存约 "
                             f"{cents_to_yuan(g['remaining'] // g['days_left'])} 元才能按时达成。")
    lines.append("建议优先保证餐饮等必要支出，非必要消费前对照每日可支配上限做判断。")
    return "\n".join(lines), basis, warnings


def local_advice(ctx: dict, question: str) -> dict:
    m = re.search(r"(\d+(?:\.\d{1,2})?)\s*(?:元|块|块钱)?", question)
    if m and re.search(r"买|花|购|消费|入手|值得", question):
        try:
            amount = yuan_to_cents(m.group(1))
            answer, basis, warnings = _answer_with_amount(ctx, amount, question)
            return {"answer": answer, "basis": basis, "warnings": warnings}
        except ValueError:
            pass
    answer, basis, warnings = _answer_general(ctx, question)
    return {"answer": answer, "basis": basis, "warnings": warnings}


def _external_advice(ctx: dict, question: str) -> dict:
    s = get_settings()
    system = (
        "你是大学生财务助手。你只能基于提供的 JSON 财务上下文回答，禁止编造未提供的收入、资产或储蓄数据；"
        "缺少某项数据时明确说明。输出 JSON：{\"answer\": \"建议文本\", \"basis\": [{\"label\": \"依据名\", \"value\": \"值\"}], "
        "\"warnings\": [\"风险提示文本\"]}。建议仅供参考，不改动任何账本数据。"
    )
    user = f"用户问题：{question}\n\n用户财务上下文（JSON）：\n{json.dumps(ctx, ensure_ascii=False)}"
    data = llm.json_reply(s.ai_api_base_url, s.ai_api_key, s.ai_model,
                          system=system, user=user, timeout=s.ai_timeout_seconds)
    return {
        "answer": str(data.get("answer") or "（外部 AI 未返回建议）")[:2000],
        "basis": [
            {"label": str(b.get("label", "依据"))[:40], "value": str(b.get("value", ""))[:120]}
            for b in (data.get("basis") or [])[:12]
        ],
        "warnings": [str(w)[:300] for w in (data.get("warnings") or [])[:6]],
    }


def advise(db: Session, user_id: int, question: str) -> dict:
    ctx = build_context(db, user_id)
    s = get_settings()
    use_external = s.ai_mode == "external" or (s.ai_mode == "auto" and s.has_llm)
    mode = "demo"
    if use_external:
        try:
            result = _external_advice(ctx, question)
            mode = "external"
            return {"mode": mode, **result, "disclaimer": DISCLAIMER}
        except Exception as e:
            result = local_advice(ctx, question)
            result["answer"] = (f"（外部 AI 调用失败：{type(e).__name__}，已回退本地演示模式）\n"
                                + result["answer"])
            return {"mode": mode, **result, "disclaimer": DISCLAIMER}
    return {"mode": mode, **local_advice(ctx, question), "disclaimer": DISCLAIMER}

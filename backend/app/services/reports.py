"""消费报告：月度 / 学期 / 年度。

周期规则（与 README 一致）：
- 月度：指定月（YYYY-MM）的自然月；不指定取上月（当月数据不完整）。
- 学期：由环境变量配置的秋季学期（默认 09-01 ~ 次年 01-20）与春季学期（02-20 ~ 07-10）；
  不指定时按今天所在学期取。
- 年度：自然年；不指定取上一年（当年数据不完整）。
"""
import logging
import math
import os
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.money import cents_to_yuan
from ..core.timeutil import app_tz, now, parse_date
from ..models import Bill, Budget, Goal, Notification, Report, User
from . import ai_advice
from .assets import current_assets

logger = logging.getLogger(__name__)

TYPE_LABELS = {"monthly": "月度", "semester": "学期", "annual": "年度"}


def _semesters(around: date, count: int = 4) -> list[dict]:
    """按配置推算学期窗口，返回 [{'label','start','end'}]，倒序。"""
    s = get_settings()
    f_s, f_e = s.semester_fall_start, s.semester_fall_end
    sp_s, sp_e = s.semester_spring_start, s.semester_spring_end

    def make(year: int, kind: str) -> dict:
        if kind == "fall":
            start = date(year, int(f_s[:2]), int(f_s[3:]))
            end = date(year + 1, int(f_e[:2]), int(f_e[3:]))
            label = f"{year}-{year + 1} 学年第一学期"
        else:
            start = date(year, int(sp_s[:2]), int(sp_s[3:]))
            end = date(year, int(sp_e[:2]), int(sp_e[3:]))
            label = f"{year - 1}-{year} 学年第二学期"
        return {"label": label, "start": start, "end": end}

    out = []
    # 当前学期
    fall_cur = make(around.year, "fall")
    spring_cur = make(around.year, "spring")
    current = fall_cur if fall_cur["start"] <= around <= fall_cur["end"] else spring_cur
    out.append(current)
    # 向前补学期
    while len(out) < count:
        last = out[-1]
        if last is current and current["start"] == fall_cur["start"]:
            nxt = make(around.year, "spring")
        elif last["start"].month == int(sp_s[:2]):
            nxt = make(last["start"].year - 1, "fall")
        else:
            nxt = make(last["start"].year - 1, "spring")
        out.append(nxt)
    return out


def resolve_period(report_type: str, period_start: str | None, period_end: str | None) -> tuple[date, date, str]:
    today = now().date()
    if report_type == "monthly":
        if period_start and len(period_start) == 7:  # YYYY-MM
            y, m = map(int, period_start.split("-"))
            start = date(y, m, 1)
            end = date(y + (m // 12), m % 12 + 1, 1) - timedelta(days=1)
            return start, end, f"{y}年{m}月"
        if period_start and period_end:
            return parse_date(period_start), parse_date(period_end), \
                f"{period_start} ~ {period_end}"
        # 默认：上月
        first_this = today.replace(day=1)
        end = first_this - timedelta(days=1)
        start = end.replace(day=1)
        return start, end, f"{start.year}年{start.month}月"
    if report_type == "semester":
        if period_start and period_end:
            return parse_date(period_start), parse_date(period_end), f"{period_start} ~ {period_end}"
        cur = _semesters(today, 1)[0]
        return cur["start"], cur["end"], cur["label"]
    if report_type == "annual":
        if period_start and len(period_start) == 4:
            y = int(period_start)
            return date(y, 1, 1), date(y, 12, 31), f"{y}年"
        if period_start and period_end:
            return parse_date(period_start), parse_date(period_end), f"{period_start} ~ {period_end}"
        y = today.year - 1
        return date(y, 1, 1), date(y, 12, 31), f"{y}年"
    raise ValueError("未知报告类型")


def _range_bills(db: Session, user_id: int, start: date, end: date):
    start_dt = datetime(start.year, start.month, start.day, tzinfo=app_tz())
    end_dt = datetime(end.year, end.month, end.day, tzinfo=app_tz()) + timedelta(days=1)
    rows = db.execute(
        select(Bill).where(
            Bill.user_id == user_id,
            Bill.bill_type.in_(["income", "expense"]),
            Bill.occurred_at >= start_dt, Bill.occurred_at < end_dt,
        ).order_by(Bill.occurred_at)
    ).scalars().all()
    return rows, start_dt, end_dt


def build_content(db: Session, user: User, report_type: str, start: date, end: date, label: str) -> dict:
    rows, start_dt, end_dt = _range_bills(db, user.id, start, end)
    expense_total = sum(b.amount_cents for b in rows if b.bill_type == "expense")
    income_total = sum(b.amount_cents for b in rows if b.bill_type == "income")

    cat_map: dict[str, int] = {}
    for b in rows:
        if b.bill_type == "expense":
            cat_map[b.category_name] = cat_map.get(b.category_name, 0) + b.amount_cents
    categories = sorted(cat_map.items(), key=lambda kv: -kv[1])
    days = max((end - start).days + 1, 1)
    avg_daily = expense_total // days
    top_cat = categories[0][0] if categories else None
    max_day = None
    day_totals: dict[str, int] = {}
    for b in rows:
        if b.bill_type == "expense":
            k = b.occurred_at.astimezone(app_tz()).strftime("%m-%d")
            day_totals[k] = day_totals.get(k, 0) + b.amount_cents
    if day_totals:
        d, v = max(day_totals.items(), key=lambda kv: kv[1])
        max_day = {"day": d, "amount_cents": v}

    # 预算执行：区间内各月总预算合计 vs 区间支出
    months = set()
    cursor = start.replace(day=1)
    while cursor <= end:
        months.add(cursor)
        cursor = (cursor + timedelta(days=32)).replace(day=1)
    budget_rows = db.execute(
        select(Budget).where(Budget.user_id == user.id, Budget.scope == "total",
                             Budget.month_start.in_([m for m in months]))
    ).scalars().all()
    budget_exec = None
    if budget_rows:
        total_budget = sum(b.amount_cents for b in budget_rows)
        usage = int(round(expense_total * 100 / total_budget)) if total_budget else 0
        budget_exec = {
            "total_cents": total_budget, "spent_cents": expense_total,
            "usage_percent": usage,
            "status": "exceeded" if usage > 100 else ("approaching" if usage >= 80 else "normal"),
        }

    # 异常消费：区间内触发过单笔异常的账单
    anomaly_bill_ids = set(db.execute(
        select(Notification.bill_id).where(
            Notification.user_id == user.id, Notification.kind == "anomaly",
            Notification.bill_id.isnot(None),
        )
    ).scalars().all())
    anomalies = [
        {"bill_id": b.id, "category_name": b.category_name, "amount_cents": b.amount_cents,
         "occurred_at": b.occurred_at.astimezone(app_tz()).strftime("%Y-%m-%d %H:%M"),
         "note": b.note}
        for b in rows if b.id in anomaly_bill_ids and b.bill_type == "expense"
    ]

    # 储蓄目标快照
    goals = db.execute(select(Goal).where(Goal.user_id == user.id)).scalars().all()
    goal_snapshot = [
        {"name": g.name, "target_cents": g.target_cents, "current_cents": g.current_cents,
         "progress_percent": int(round(g.current_cents * 100 / g.target_cents)) if g.target_cents else 0,
         "deadline": g.deadline.isoformat()}
        for g in goals
    ]

    assets = current_assets(db, user.id)
    advice = ai_advice.local_advice(ai_advice.build_context(db, user.id), "帮我总结一下近期的消费情况")

    return {
        "summary": {
            "period_label": label, "period_start": start.isoformat(), "period_end": end.isoformat(),
            "expense_cents": expense_total, "income_cents": income_total,
            "net_cents": income_total - expense_total, "bill_count": len(rows),
            "avg_daily_cents": avg_daily, "top_category": top_cat,
            "max_day": max_day, "current_assets_cents": assets,
        },
        "categories": [
            {"category_name": n, "amount_cents": a,
             "percent": round(a * 100 / expense_total, 1) if expense_total else 0.0}
            for n, a in categories
        ],
        "budget": budget_exec,
        "anomalies": anomalies,
        "goals": goal_snapshot,
        "advice": advice["answer"],
        "generated_at": now().isoformat(timespec="seconds"),
    }


def periods_options() -> dict:
    today = now().date()
    months = []
    for i in range(12):
        d = (today.replace(day=1) - timedelta(days=i * 32)).replace(day=1)
        months.append(f"{d.year}-{d.month:02d}")
    return {
        "monthly": months,
        "semesters": [
            {"label": s["label"], "start": s["start"].isoformat(), "end": s["end"].isoformat()}
            for s in _semesters(today, 4)
        ],
        "years": [str(today.year - i) for i in range(5)],
    }


# ---------------- PDF（reportlab，中文用内置 CID 字体，无需字体文件） ----------------
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.cidfonts import UnicodeCIDFont  # noqa: E402
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # noqa: E402

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

_ST_TITLE = ParagraphStyle("title", fontName="STSong-Light", fontSize=18, leading=26,
                           alignment=1, spaceAfter=6)
_ST_H2 = ParagraphStyle("h2", fontName="STSong-Light", fontSize=13, leading=18,
                        spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#1a3c6e"))
_ST_BODY = ParagraphStyle("body", fontName="STSong-Light", fontSize=10.5, leading=16)


def generate_pdf(report: Report, export_dir: str) -> str:
    c = report.content
    s = c["summary"]
    fname = f"report_{report.user_id}_{report.id}.pdf"
    path = os.path.join(export_dir, fname)
    os.makedirs(export_dir, exist_ok=True)
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm, title=report.title)
    story = [
        Paragraph(report.title, _ST_TITLE),
        Paragraph(f"统计周期：{s['period_label']}（{s['period_start']} ~ {s['period_end']}）　"
                  f"生成时间：{c.get('generated_at', '')}", _ST_BODY),
        Spacer(1, 8),
        Paragraph("一、消费总览", _ST_H2),
        Paragraph(
            f"总支出 <b>{cents_to_yuan(s['expense_cents'])} 元</b>；总收入 {cents_to_yuan(s['income_cents'])} 元；"
            f"结余 {cents_to_yuan(s['net_cents'])} 元；账单 {s['bill_count']} 笔；"
            f"日均支出约 {cents_to_yuan(s['avg_daily_cents'])} 元。", _ST_BODY),
    ]
    if s.get("top_category"):
        story.append(Paragraph(f"最大支出类别：{s['top_category']}。", _ST_BODY))
    if s.get("max_day"):
        story.append(Paragraph(
            f"单日最高支出：{s['max_day']['day']}，{cents_to_yuan(s['max_day']['amount_cents'])} 元。", _ST_BODY))

    story.append(Paragraph("二、分类消费", _ST_H2))
    if c["categories"]:
        data = [["分类", "金额（元）", "占比"]]
        for row in c["categories"]:
            data.append([row["category_name"], cents_to_yuan(row["amount_cents"]), f"{row['percent']}%"])
        tbl = Table(data, colWidths=[60 * mm, 60 * mm, 40 * mm])
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")),
            ("ALIGN", (1, 1), (2, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story += [tbl, Spacer(1, 6)]
    else:
        story.append(Paragraph("该周期内没有支出记录。", _ST_BODY))

    story.append(Paragraph("三、预算执行", _ST_H2))
    b = c.get("budget")
    if b:
        status = {"exceeded": "已超支", "approaching": "接近上限", "normal": "正常"}[b["status"]]
        story.append(Paragraph(
            f"区间总预算 {cents_to_yuan(b['total_cents'])} 元，实际支出 {cents_to_yuan(b['spent_cents'])} 元，"
            f"使用率 {b['usage_percent']}%（{status}）。", _ST_BODY))
    else:
        story.append(Paragraph("该周期内未设置预算。", _ST_BODY))

    story.append(Paragraph("四、异常消费", _ST_H2))
    if c["anomalies"]:
        for a in c["anomalies"]:
            story.append(Paragraph(
                f"· {a['occurred_at']}　{a['category_name']}　{cents_to_yuan(a['amount_cents'])} 元"
                + (f"（{a['note']}）" if a["note"] else ""), _ST_BODY))
    else:
        story.append(Paragraph("该周期内未发现异常消费。", _ST_BODY))

    story.append(Paragraph("五、储蓄目标", _ST_H2))
    if c["goals"]:
        for g in c["goals"]:
            story.append(Paragraph(
                f"· {g['name']}：{cents_to_yuan(g['current_cents'])} / {cents_to_yuan(g['target_cents'])} 元"
                f"（{g['progress_percent']}%），截止 {g['deadline']}", _ST_BODY))
    else:
        story.append(Paragraph("未设置储蓄目标。", _ST_BODY))

    story.append(Paragraph("六、建议", _ST_H2))
    for line in c.get("advice", "").split("\n"):
        story.append(Paragraph(line, _ST_BODY))
    story.append(Spacer(1, 8))
    story.append(Paragraph("本报告由大学生智能财务管理平台生成，仅供个人理财参考。", _ST_BODY))
    doc.build(story)
    return fname

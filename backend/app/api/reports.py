"""消费报告：生成 / 列表 / 查看 / PDF 导出 / 历史下载（扩展需求）。"""
import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.deps import get_current_user, get_db
from ..core.errors import biz_error, not_found
from ..models import Report, User
from ..schemas.report import ReportGenerateIn, ReportListOut, ReportOut, ReportPeriodsOut
from ..services import reports as report_svc

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/periods", response_model=ReportPeriodsOut)
def report_periods(user: User = Depends(get_current_user)):
    return report_svc.periods_options()


@router.post("/generate", response_model=ReportOut, status_code=201)
def generate(body: ReportGenerateIn, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    start, end, label = report_svc.resolve_period(
        body.report_type, body.period_start, body.period_end
    )
    content = report_svc.build_content(db, user, body.report_type, start, end, label)
    report = Report(
        user_id=user.id, report_type=body.report_type, period_start=start, period_end=end,
        title=f"{report_svc.TYPE_LABELS[body.report_type]}消费报告（{label}）",
        content=content,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return _to_out(report)


def _to_out(r: Report) -> ReportOut:
    return ReportOut(
        id=r.id, report_type=r.report_type, period_start=r.period_start,
        period_end=r.period_end, title=r.title, content=r.content,
        has_pdf=bool(r.pdf_path), created_at=r.created_at,
    )


@router.get("", response_model=ReportListOut)
def list_reports(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Report).where(Report.user_id == user.id).order_by(Report.created_at.desc())
    ).scalars().all()
    return ReportListOut(items=[_to_out(r) for r in rows])


def _own_report(db: Session, user: User, report_id: int) -> Report:
    r = db.get(Report, report_id)
    if r is None or r.user_id != user.id:
        raise not_found("报告不存在")
    return r


@router.get("/{report_id}", response_model=ReportOut)
def get_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _to_out(_own_report(db, user, report_id))


@router.get("/{report_id}/pdf")
def download_pdf(report_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    r = _own_report(db, user, report_id)
    export_dir = os.path.abspath(get_settings().export_dir)
    if r.pdf_path and os.path.exists(os.path.join(export_dir, r.pdf_path)):
        path = os.path.join(export_dir, r.pdf_path)
    else:
        try:
            fname = report_svc.generate_pdf(r, export_dir)
        except Exception as e:
            raise biz_error("PDF_GENERATE_FAILED", f"PDF 生成失败：{type(e).__name__}，请稍后重试", 500)
        r.pdf_path = fname
        db.commit()
        path = os.path.join(export_dir, fname)
    if not os.path.exists(path):
        raise biz_error("PDF_GENERATE_FAILED", "报告文件不存在或已失效，请重新生成", 404)
    return FileResponse(path, media_type="application/pdf",
                        filename=f"{r.report_type}_{r.period_start}_{r.period_end}.pdf")


@router.delete("/{report_id}", status_code=204)
def delete_report(report_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    r = _own_report(db, user, report_id)
    if r.pdf_path:
        p = os.path.join(os.path.abspath(get_settings().export_dir), r.pdf_path)
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    db.delete(r)
    db.commit()

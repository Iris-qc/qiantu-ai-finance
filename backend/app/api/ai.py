"""AI 模块：自然语言 / 语音 / 图片识别只生成草稿；确认后才写入正式账单。

外部服务未配置时：自然语言走明确标注的本地演示解析；语音、图片返回"未配置"提示。
任何草稿的失败、取消或字段缺失都不会改变正式账单、资产和预算。
"""
from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.deps import get_current_user, get_db
from ..core.errors import biz_error, unconfigured
from ..models import Bill, User
from ..schemas.ai import (AdviceIn, AdviceOut, DraftConfirmIn, DraftConfirmOut,
                          DraftItem, NlParseIn, NlParseOut, OcrParseOut, SpeechParseOut)
from ..services import ai_advice, anomalies, budgets, parsing
from ..services.providers import ocr, speech
from ..core import timeutil

router = APIRouter(prefix="/ai", tags=["ai"])

MAX_UPLOAD = 10 * 1024 * 1024  # 10MB


@router.post("/drafts/nl", response_model=NlParseOut)
def parse_nl(body: NlParseIn, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    try:
        mode, notice, items = parsing.parse_nl(db, user.id, body.text)
    except parsing.ParseFailure as e:
        raise biz_error("PARSE_FAILED", str(e))
    return NlParseOut(mode=mode, notice=notice, items=[DraftItem(**i) for i in items])


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise biz_error("FILE_TOO_LARGE", "文件不能超过 10MB")
    return data


@router.post("/drafts/speech", response_model=SpeechParseOut)
async def parse_speech(file: UploadFile, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    s = get_settings()
    if not s.has_speech:
        raise unconfigured(
            "语音识别服务未配置（SPEECH_API_BASE_URL / SPEECH_API_KEY 为空）。"
            "请配置外部语音转写服务后重试，或使用自然语言/手动记账。"
        )
    audio = await _read_upload(file)
    try:
        transcript = speech.transcribe(s.speech_api_base_url, s.speech_api_key,
                                       s.speech_model, audio, filename=file.filename or "audio.webm",
                                       timeout=s.ai_timeout_seconds)
    except Exception as e:
        raise biz_error("SPEECH_FAILED", f"语音转写失败：{type(e).__name__}，建议手动记账", 502)
    try:
        mode, notice, items = parsing.parse_nl(db, user.id, transcript)
    except parsing.ParseFailure as e:
        raise biz_error("PARSE_FAILED", "语音识别到内容但没有有效消费信息，请重新录制或手动记账")
    return SpeechParseOut(mode=mode, transcript=transcript, items=[DraftItem(**i) for i in items],
                          notice="已调用外部语音转写服务。" + notice)


@router.post("/drafts/image", response_model=OcrParseOut)
async def parse_image(file: UploadFile, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    s = get_settings()
    if not s.has_ocr:
        raise unconfigured(
            "图片识别服务未配置（OCR_API_BASE_URL / OCR_API_KEY 为空）。"
            "请配置外部 OCR 服务后重试，或使用自然语言/手动记账。"
        )
    data = await _read_upload(file)
    mime = file.content_type or "image/jpeg"
    if not mime.startswith("image/"):
        raise biz_error("BAD_IMAGE", "请上传图片文件（jpg/png/webp 等）")
    try:
        text = ocr.ocr_image(s.ocr_api_base_url, s.ocr_api_key, s.ocr_model,
                             data, mime=mime, timeout=s.ai_timeout_seconds)
    except Exception as e:
        raise biz_error("OCR_FAILED", f"图片识别失败：{type(e).__name__}，建议手动记账", 502)
    try:
        mode, notice, items = parsing.parse_nl(db, user.id, text)
    except parsing.ParseFailure as e:
        raise biz_error("PARSE_FAILED", "图片中未能识别出消费信息，请换一张清晰的图片或手动录入")
    return OcrParseOut(mode=mode, ocr_text=text[:2000], items=[DraftItem(**i) for i in items],
                       notice="已调用外部 OCR 服务。" + notice)


@router.post("/drafts/confirm", response_model=DraftConfirmOut, status_code=201)
def confirm_drafts(body: DraftConfirmIn, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """批量确认草稿：先全部校验，任一不合法则整体拒绝（不写入任何账单）。"""
    from ..api.categories import _get_owned  # 复用分类归属校验

    errors: list[dict] = []
    for i, item in enumerate(body.items):
        if item.amount_cents <= 0:
            errors.append({"index": i, "reason": "金额必须大于 0"})
            continue
        if item.category_id is not None:
            from ..models import Category
            cat = db.get(Category, item.category_id)
            if cat is None or cat.deleted_at is not None or \
                    (cat.user_id is not None and cat.user_id != user.id):
                errors.append({"index": i, "reason": f"第 {i + 1} 条草稿的分类不存在"})
            elif cat.kind != item.bill_type:
                errors.append({"index": i, "reason": f"分类「{cat.name}」与收支类型不匹配"})
        else:
            # 按名称匹配现有分类
            from ..models import Category
            cat = db.execute(
                __import__("sqlalchemy").select(Category).where(
                    (Category.user_id == user.id) | (Category.user_id.is_(None)),
                    Category.name == item.category_name, Category.kind == item.bill_type,
                    Category.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if cat is not None:
                item.category_id = cat.id
            else:
                errors.append({"index": i, "reason":
                               f"分类「{item.category_name}」不存在，请在草稿中选择已有分类"})
    if errors:
        raise biz_error("DRAFT_VALIDATION_FAILED",
                        "部分草稿字段不合法，已拒绝全部保存（不会写入任何账单）",
                        422, fields={"items": errors})

    created_ids = []
    for item in body.items:
        bill = Bill(
            user_id=user.id, bill_type=item.bill_type, amount_cents=item.amount_cents,
            category_id=item.category_id, category_name=item.category_name,
            occurred_at=timeutil.as_app_tz(item.occurred_at) if item.occurred_at else timeutil.now(),
            note=item.note, source=body.source,
        )
        db.add(bill)
        db.flush()
        budgets.sync_budget_for_month(db, user.id, timeutil.local_date(bill.occurred_at))
        anomalies.evaluate_bill(db, bill)
        created_ids.append(bill.id)
    db.commit()
    return DraftConfirmOut(created=created_ids)


@router.post("/advice", response_model=AdviceOut)
def advice(body: AdviceIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = ai_advice.advise(db, user.id, body.question)
    return AdviceOut(**result)

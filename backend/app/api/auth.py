"""认证：注册 / 登录（含连续失败锁定）/ 当前用户 / 邮箱验证码找回密码（扩展需求）。"""
import logging
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import timeutil
from ..core.config import get_settings
from ..core.deps import get_current_user, get_db
from ..core.errors import biz_error, unconfigured
from ..core.security import create_access_token, hash_code, hash_password, verify_code, verify_password
from ..models import PasswordResetCode, User
from ..schemas.auth import LoginIn, RegisterIn, ResetConfirmIn, ResetRequestIn, TokenOut
from ..schemas.common import UserOut
from ..services.providers import mail

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    exists = db.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    if exists:
        raise biz_error("USERNAME_TAKEN", "该用户名已被注册")
    if body.email:
        email_exists = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
        if email_exists:
            raise biz_error("EMAIL_TAKEN", "该邮箱已被其他账号绑定")
    user = User(username=body.username, password_hash=hash_password(body.password),
                email=str(body.email) if body.email else None)
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    s = get_settings()
    user = db.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    now = timeutil.now()
    if user is not None and user.locked_until is not None and user.locked_until > now:
        raise biz_error(
            "ACCOUNT_LOCKED",
            f"连续 {s.login_max_failures} 次登录失败，账号已锁定，请 "
            f"{int((user.locked_until - now).total_seconds() // 60) + 1} 分钟后再试",
            403,
        )
    if user is None or not verify_password(body.password, user.password_hash):
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= s.login_max_failures:
                user.locked_until = now + timedelta(minutes=s.login_lock_minutes)
                user.failed_login_count = 0
                db.commit()
                raise biz_error(
                    "ACCOUNT_LOCKED",
                    f"连续 {s.login_max_failures} 次登录失败，账号已锁定 "
                    f"{s.login_lock_minutes} 分钟",
                    403,
                )
            db.commit()
        raise biz_error("BAD_CREDENTIALS", "用户名或密码错误", 401)
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


def _send_reset_code(db: Session, email: str) -> str:
    """生成验证码并尽力发送。返回给前端的说明文本；SMTP 未配置时写入日志并明确告知。"""
    s = get_settings()
    code = f"{secrets.randbelow(1000000):06d}"
    db.add(PasswordResetCode(
        email=email, code_hash=hash_code(code),
        expires_at=timeutil.now() + timedelta(minutes=s.reset_code_minutes),
    ))
    db.commit()
    if s.has_smtp:
        try:
            mail.send_mail(
                email, "CSAIFM 找回密码验证码",
                f"你的验证码是 {code}，{s.reset_code_minutes} 分钟内有效。若非本人操作请忽略。",
            )
            return "验证码已发送至你的邮箱，5 分钟内有效"
        except Exception as e:
            logger.error("发送验证码邮件失败: %s", e)
            raise biz_error("MAIL_SEND_FAILED", "验证码邮件发送失败，请稍后重试", 503)
    # 开发/演示环境：未配置 SMTP，验证码只出现在后端日志中（不冒充发送成功）
    logger.warning("【演示】未配置 SMTP，验证码 %s（邮箱 %s）仅写入日志，未真实发送", code, email)
    raise unconfigured(
        "邮件服务未配置（SMTP 环境变量为空）。验证码已写入后端日志，仅用于本地演示；"
        "配置 SMTP 后可真实发送邮件。"
    )


@router.post("/password-reset/request", status_code=202)
def request_reset(body: ResetRequestIn, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == str(body.email))).scalar_one_or_none()
    if user is None:
        raise biz_error("EMAIL_NOT_FOUND", "该邮箱未注册", 404)
    message = _send_reset_code(db, str(body.email))
    return {"message": message}


@router.post("/password-reset/confirm")
def confirm_reset(body: ResetConfirmIn, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == str(body.email))).scalar_one_or_none()
    if user is None:
        raise biz_error("EMAIL_NOT_FOUND", "该邮箱未注册", 404)
    row = db.execute(
        select(PasswordResetCode)
        .where(PasswordResetCode.email == str(body.email), PasswordResetCode.used.is_(False))
        .order_by(PasswordResetCode.id.desc())
    ).scalars().first()
    if row is None or row.expires_at < timeutil.now() or not verify_code(body.code, row.code_hash):
        raise biz_error("INVALID_CODE", "验证码无效或已过期，请重新获取")
    row.used = True
    user.password_hash = hash_password(body.new_password)
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()
    return {"message": "密码已重置，请使用新密码登录"}

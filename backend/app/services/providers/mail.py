"""邮件发送适配（SMTP）。未配置时由上层返回"未配置"。"""
import logging
import smtplib
import ssl
from email.header import Header
from email.mime.text import MIMEText

from ...core.config import get_settings

logger = logging.getLogger(__name__)


def send_mail(to: str, subject: str, body: str) -> None:
    s = get_settings()
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = s.smtp_from
    msg["To"] = to
    if s.smtp_use_tls:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=ctx, timeout=15) as server:
            server.login(s.smtp_user, s.smtp_password)
            server.sendmail(s.smtp_from, [to], msg.as_string())
    else:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as server:
            server.login(s.smtp_user, s.smtp_password)
            server.sendmail(s.smtp_from, [to], msg.as_string())

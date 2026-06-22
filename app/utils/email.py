"""
邮件发送工具 - 基于 SMTP
支持：普通文本邮件、HTML 邮件、附件
"""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from email.utils import formataddr

from app.config import settings
from app.core.validators import validate_email

logger = logging.getLogger("app")


def _get_smtp_server():
    """创建并返回 SMTP 连接"""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        raise RuntimeError("SMTP 配置未填写，请在 .env 中配置 SMTP_USER 和 SMTP_PASSWORD")

    if settings.SMTP_USE_SSL:
        server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
        server.starttls()

    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
    return server


def send_email(to_email: str, subject: str, body: str, html: bool = False,
               attachments: list = None) -> bool:
    """
    发送邮件
    :param to_email: 收件人邮箱
    :param subject: 邮件主题
    :param body: 邮件正文
    :param html: 是否为 HTML 格式
    :param attachments: 附件列表，每项为 {"path": str, "filename": str}
    :return: 是否发送成功
    """
    # 校验邮箱
    valid, msg = validate_email(to_email)
    if not valid:
        logger.warning(f"无效的邮箱地址: {to_email} ({msg})")
        return False

    try:
        # 创建邮件
        if attachments:
            msg = MIMEMultipart()
            content_type = "html" if html else "plain"
            msg.attach(MIMEText(body, content_type, "utf-8"))
        else:
            content_type = "html" if html else "plain"
            msg = MIMEText(body, content_type, "utf-8")

        # 发件人
        msg["From"] = formataddr((str(Header(settings.SMTP_FROM_NAME, "utf-8")), settings.SMTP_USER))
        msg["To"] = to_email
        msg["Subject"] = Header(subject, "utf-8")

        # 添加附件
        if attachments:
            for att in attachments:
                file_path = att.get("path")
                filename = att.get("filename") or os.path.basename(file_path)

                if not file_path or not os.path.exists(file_path):
                    logger.warning(f"附件不存在: {file_path}")
                    continue

                with open(file_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{Header(filename, "utf-8")}"',
                )
                msg.attach(part)

        # 发送
        server = _get_smtp_server()
        try:
            server.sendmail(settings.SMTP_USER, [to_email], msg.as_string())
            logger.info(f"邮件已发送至 {to_email}")
        finally:
            try:
                server.quit()
            except Exception:
                pass

        return True

    except Exception as e:
        logger.error(f"邮件发送失败 (to: {to_email}): {e}")
        return False


def send_verification_code(to_email: str, code: str) -> bool:
    """
    发送验证码邮件
    :param to_email: 收件人邮箱
    :param code: 6位验证码
    :return: 是否成功
    """
    subject = "【学生信息管理系统】密码重置验证码"
    body = f"""
    <div style="font-family: 'Microsoft YaHei', Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 24px; color: #fff; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">密码重置</h2>
        </div>
        <div style="padding: 24px; background: #fff; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
            <p style="font-size: 14px; color: #374151;">您好，</p>
            <p style="font-size: 14px; color: #374151;">您正在申请重置密码，验证码为：</p>
            <div style="text-align: center; padding: 24px; margin: 16px 0; background: #f3f4f6; border-radius: 8px;">
                <span style="font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #667eea;">{code}</span>
            </div>
            <p style="font-size: 14px; color: #6b7280;">验证码有效期为 <strong>10 分钟</strong>，请勿将验证码告知他人。</p>
            <p style="font-size: 14px; color: #6b7280;">如非本人操作，请忽略此邮件。</p>
            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
            <p style="font-size: 12px; color: #9ca3af;">—— 学生信息管理系统</p>
        </div>
    </div>
    """
    return send_email(to_email, subject, body, html=True)

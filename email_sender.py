"""
邮件发送模块 — 通过 SMTP 发送 HTML 格式日报和测试邮件。
支持 TLS/SSL，兼容 Gmail / QQ邮箱 / 163 等主流邮箱。
"""

from __future__ import annotations

import smtplib
import ssl
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from logger import get_logger

logger = get_logger()


def send_test_email(config: dict[str, Any]) -> tuple[bool, str]:
    """
    发送一封测试邮件，验证 SMTP 配置是否正确。
    返回 (成功标志, 消息)。
    """
    recipient = config.get("recipient_email", "").strip()
    if not recipient:
        return False, "收件人邮箱未设置"

    smtp_server = config.get("smtp_server", "").strip()
    smtp_port = config.get("smtp_port", 587)
    sender_email = config.get("sender_email", "").strip()
    sender_password = config.get("sender_password", "").strip()
    use_tls = config.get("smtp_use_tls", True)

    if not all([smtp_server, sender_email, sender_password]):
        return False, "SMTP 配置不完整，请填写服务器、发件人和授权码"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "[测试邮件] 全球每日新闻日报推送器 - Test Email"
        msg["From"] = sender_email
        msg["To"] = recipient

        html_body = f"""
        <html><body style="font-family:Arial,sans-serif;padding:20px;">
        <h2 style="color:#1a237e;">测试邮件 Test Email</h2>
        <p>如果您收到此邮件，说明 SMTP 配置正确。</p>
        <p>If you received this email, your SMTP configuration is working correctly.</p>
        <hr style="border:1px solid #e0e0e0;">
        <p style="color:#999;font-size:12px;">
          发送时间 Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
          全球每日新闻日报推送器 | Daily Global News Briefing System
        </p>
        </body></html>
        """
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        if use_tls:
            context = ssl.create_default_context()
            # QQ 邮箱等国内服务可能拒绝默认 TLS 协商，强制兼容配置
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient, msg.as_string())
        else:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30, context=context) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient, msg.as_string())

        logger.info("测试邮件发送成功 → %s", recipient)
        return True, f"测试邮件已发送到 {recipient}"
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP 认证失败")
        return False, "SMTP 认证失败，请检查邮箱地址和授权码"
    except smtplib.SMTPConnectError:
        logger.error("SMTP 连接失败: %s:%d", smtp_server, smtp_port)
        return False, f"无法连接到 SMTP 服务器 {smtp_server}:{smtp_port}"
    except Exception as e:
        logger.error("发送测试邮件异常: %s", e)
        return False, f"发送失败: {e}"


def send_daily_report(
    html_content: str,
    config: dict[str, Any],
) -> tuple[bool, str]:
    """
    发送日报 HTML 邮件。
    返回 (成功标志, 消息)。
    """
    recipient = config.get("recipient_email", "").strip()
    if not recipient:
        return False, "收件人邮箱未设置"

    smtp_server = config.get("smtp_server", "").strip()
    smtp_port = config.get("smtp_port", 587)
    sender_email = config.get("sender_email", "").strip()
    sender_password = config.get("sender_password", "").strip()
    use_tls = config.get("smtp_use_tls", True)

    if not all([smtp_server, sender_email, sender_password]):
        return False, "SMTP 配置不完整"

    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz)
    date_str = today.strftime("%Y-%m-%d")

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"每日全球新闻简报 - {date_str} | Daily Global News Briefing"
        msg["From"] = sender_email
        msg["To"] = recipient
        msg["Date"] = today.strftime("%a, %d %b %Y %H:%M:%S +0800")

        msg.attach(MIMEText(html_content, "html", "utf-8"))

        if use_tls:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            with smtplib.SMTP(smtp_server, smtp_port, timeout=60) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient, msg.as_string())
        else:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=60, context=context) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient, msg.as_string())

        logger.info("日报邮件发送成功 → %s", recipient)
        return True, f"日报已发送到 {recipient}"
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP 认证失败，请检查邮箱地址和授权码"
    except smtplib.SMTPConnectError:
        return False, f"无法连接到 SMTP 服务器 {smtp_server}:{smtp_port}"
    except Exception as e:
        logger.error("发送日报邮件异常: %s", e)
        return False, f"发送失败: {e}"

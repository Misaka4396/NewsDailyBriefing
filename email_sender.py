"""
邮件发送模块 — 通过 SMTP 发送 HTML 格式日报和测试邮件。
支持 TLS/SSL，兼容 Gmail / QQ邮箱 / 163 等主流邮箱。
"""

from __future__ import annotations

import smtplib
import socket
import ssl
import time
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from logger import get_logger

logger = get_logger()

MAX_RETRIES = 3
RETRY_DELAY = 3  # 秒


def _create_ssl_context() -> ssl.SSLContext:
    """创建兼容国内邮件服务的 SSL context。"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _test_connectivity(host: str, port: int, timeout: int = 10) -> str | None:
    """测试 SMTP 服务器是否可达。返回 None 表示可达，否则返回错误描述。"""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return None
    except socket.timeout:
        return f"连接 {host}:{port} 超时（{timeout}秒），请检查网络或防火墙是否放行该端口"
    except socket.gaierror:
        return f"无法解析域名 {host}，请检查 SMTP 服务器地址是否正确"
    except OSError as e:
        return f"网络错误: {e}"


def _smtp_send(
    smtp_server: str,
    smtp_port: int,
    sender_email: str,
    sender_password: str,
    recipient: str,
    msg: MIMEMultipart,
    use_tls: bool,
    timeout: int,
) -> None:
    """执行 SMTP 发送，含重试逻辑。"""

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if use_tls:
                with smtplib.SMTP(smtp_server, smtp_port, timeout=timeout) as server:
                    server.set_debuglevel(0)
                    server.ehlo()
                    server.starttls(context=_create_ssl_context())
                    server.ehlo()
                    server.login(sender_email, sender_password)
                    server.sendmail(sender_email, recipient, msg.as_string())
            else:
                with smtplib.SMTP_SSL(
                    smtp_server, smtp_port, timeout=timeout, context=_create_ssl_context()
                ) as server:
                    server.login(sender_email, sender_password)
                    server.sendmail(sender_email, recipient, msg.as_string())
            return  # 成功
        except (socket.timeout, ConnectionError, OSError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                logger.warning("SMTP 发送第 %d/%d 次失败，%d秒后重试: %s",
                               attempt, MAX_RETRIES, RETRY_DELAY, e)
                time.sleep(RETRY_DELAY)
        except smtplib.SMTPAuthenticationError:
            raise  # 认证失败不重试
        except smtplib.SMTPConnectError:
            raise  # 连接失败不重试

    raise last_error  # type: ignore[misc]


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

    # 预检：测试服务器可达性
    conn_error = _test_connectivity(smtp_server, smtp_port)
    if conn_error:
        logger.error("SMTP 服务器不可达: %s", conn_error)
        return False, conn_error

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

        _smtp_send(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            sender_email=sender_email,
            sender_password=sender_password,
            recipient=recipient,
            msg=msg,
            use_tls=use_tls,
            timeout=30,
        )

        logger.info("测试邮件发送成功 → %s", recipient)
        return True, f"测试邮件已发送到 {recipient}"
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP 认证失败")
        return False, "SMTP 认证失败，请检查邮箱地址和授权码（不是登录密码）"
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

    # 预检：测试服务器可达性
    conn_error = _test_connectivity(smtp_server, smtp_port)
    if conn_error:
        logger.error("SMTP 服务器不可达: %s", conn_error)
        return False, conn_error

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

        _smtp_send(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            sender_email=sender_email,
            sender_password=sender_password,
            recipient=recipient,
            msg=msg,
            use_tls=use_tls,
            timeout=60,
        )

        logger.info("日报邮件发送成功 → %s", recipient)
        return True, f"日报已发送到 {recipient}"
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP 认证失败，请检查邮箱地址和授权码（不是登录密码）"
    except smtplib.SMTPConnectError:
        return False, f"无法连接到 SMTP 服务器 {smtp_server}:{smtp_port}"
    except Exception as e:
        logger.error("发送日报邮件异常: %s", e)
        return False, f"发送失败: {e}"

"""
配置管理模块 — 加密存储用户配置（邮箱、API密钥等敏感信息）。
使用 cryptography.fernet 对敏感字段进行加密。
"""

from __future__ import annotations

import base64
import json
import os
import hashlib
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

from logger import get_logger

CONFIG_DIR = Path(__file__).parent / "config"
CONFIG_FILE = CONFIG_DIR / "settings.json"
KEY_FILE = CONFIG_DIR / ".key"

# 默认配置模板
DEFAULT_CONFIG: dict[str, Any] = {
    "countries": [],
    "currencies": ["EUR", "GBP", "JPY", "KRW", "INR", "CAD", "MXN", "RUB"],
    "recipient_email": "",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_use_tls": True,
    "sender_email": "",
    "sender_password": "",  # 加密存储
    "newsapi_key": "",       # 加密存储
    "gnews_key": "",         # 加密存储
}

SENSITIVE_KEYS = {"sender_password", "newsapi_key", "gnews_key"}

logger = get_logger()


def _derive_key() -> bytes:
    """基于机器标识派生加密密钥。"""
    machine_id = os.environ.get("COMPUTERNAME", "") + os.environ.get("USERNAME", "")
    seed = "news_daily_app_2024_salt"
    digest = hashlib.sha256((machine_id + seed).encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _get_cipher() -> Fernet:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if KEY_FILE.exists():
        key = KEY_FILE.read_bytes()
    else:
        key = _derive_key()
        KEY_FILE.write_bytes(key)
    return Fernet(key)


def _encrypt_value(value: str) -> str:
    if not value:
        return ""
    cipher = _get_cipher()
    return cipher.encrypt(value.encode()).decode()


def _decrypt_value(value: str) -> str:
    if not value:
        return ""
    cipher = _get_cipher()
    return cipher.decrypt(value.encode()).decode()


def load_config() -> dict[str, Any]:
    """加载配置，解密敏感字段。"""
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("配置文件损坏，使用默认配置: %s", e)
        return dict(DEFAULT_CONFIG)

    config = dict(DEFAULT_CONFIG)
    config.update(raw)

    # 解密敏感字段
    for key in SENSITIVE_KEYS:
        if config.get(key):
            try:
                config[key] = _decrypt_value(config[key])
            except Exception:
                config[key] = ""

    return config


def save_config(config: dict[str, Any]) -> bool:
    """保存配置，加密敏感字段。"""
    os.makedirs(CONFIG_DIR, exist_ok=True)

    to_save = dict(config)
    for key in SENSITIVE_KEYS:
        if to_save.get(key):
            to_save[key] = _encrypt_value(to_save[key])

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(to_save, f, ensure_ascii=False, indent=2)
        logger.info("配置已保存")
        return True
    except OSError as e:
        logger.error("保存配置失败: %s", e)
        return False


# ── 国家/货币常量 ───────────────────────────────────────────

COUNTRIES: dict[str, list[tuple[str, str]]] = {
    "欧洲 Europe": [
        ("gb", "英国 UK"),
        ("de", "德国 Germany"),
        ("fr", "法国 France"),
        ("it", "意大利 Italy"),
        ("es", "西班牙 Spain"),
        ("ru", "俄罗斯 Russia"),
    ],
    "亚洲 Asia": [
        ("cn", "中国 China"),
        ("jp", "日本 Japan"),
        ("kr", "韩国 South Korea"),
        ("in", "印度 India"),
        ("sg", "新加坡 Singapore"),
    ],
    "北美 North America": [
        ("us", "美国 USA"),
        ("ca", "加拿大 Canada"),
        ("mx", "墨西哥 Mexico"),
    ],
}

CURRENCIES: list[tuple[str, str]] = [
    ("EUR", "欧元 Euro"),
    ("GBP", "英镑 British Pound"),
    ("JPY", "日元 Japanese Yen"),
    ("KRW", "韩元 South Korean Won"),
    ("INR", "印度卢比 Indian Rupee"),
    ("CAD", "加拿大元 Canadian Dollar"),
    ("MXN", "墨西哥比索 Mexican Peso"),
    ("RUB", "俄罗斯卢布 Russian Ruble"),
    ("AUD", "澳大利亚元 Australian Dollar"),
    ("CHF", "瑞士法郎 Swiss Franc"),
    ("SGD", "新加坡元 Singapore Dollar"),
    ("HKD", "港元 Hong Kong Dollar"),
]

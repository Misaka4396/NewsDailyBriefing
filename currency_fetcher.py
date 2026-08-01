"""
汇率抓取模块 — 使用 frankfurter.app 免费 API 获取实时汇率。
获取当日及上一交易日汇率，计算涨跌幅。
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from logger import get_logger

logger = get_logger()

BASE_URL = "https://api.frankfurter.app"
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_FILE = CACHE_DIR / "currency_cache.json"
CACHE_TTL = 7200  # 2 小时


@dataclass
class CurrencyRate:
    code: str
    name: str
    name_cn: str
    rate_to_cny: float
    rate_to_usd: float
    prev_rate_to_cny: float
    prev_rate_to_usd: float
    change_pct_cny: float
    change_pct_usd: float
    updated_at: str


CURRENCY_NAMES: dict[str, tuple[str, str]] = {
    "EUR": ("Euro", "欧元"),
    "GBP": ("British Pound", "英镑"),
    "JPY": ("Japanese Yen", "日元"),
    "KRW": ("South Korean Won", "韩元"),
    "INR": ("Indian Rupee", "印度卢比"),
    "CAD": ("Canadian Dollar", "加拿大元"),
    "MXN": ("Mexican Peso", "墨西哥比索"),
    "RUB": ("Russian Ruble", "俄罗斯卢布"),
    "AUD": ("Australian Dollar", "澳大利亚元"),
    "CHF": ("Swiss Franc", "瑞士法郎"),
    "SGD": ("Singapore Dollar", "新加坡元"),
    "HKD": ("Hong Kong Dollar", "港元"),
}


def _ensure_cache_dir() -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)


def _load_cache() -> dict[str, Any]:
    """加载本地缓存。"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_cache(data: dict[str, Any]) -> None:
    _ensure_cache_dir()
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning("保存汇率缓存失败: %s", e)


def _get_latest_rates(base: str = "USD") -> dict[str, float]:
    """获取最新汇率（以 base 为基准）。"""
    try:
        resp = requests.get(f"{BASE_URL}/latest", params={"from": base}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("rates", {})
    except Exception as e:
        logger.error("获取最新汇率失败 [%s]: %s", base, e)
        return {}


def _get_historical_rates(date_str: str, base: str = "USD") -> dict[str, float]:
    """获取历史汇率。"""
    try:
        resp = requests.get(f"{BASE_URL}/{date_str}", params={"from": base}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("rates", {})
    except Exception as e:
        logger.warning("获取历史汇率失败 [%s @ %s]: %s", base, date_str, e)
        return {}


def fetch_rates(currency_codes: list[str]) -> list[CurrencyRate]:
    """
    获取指定货币对 CNY 和 USD 的汇率及涨跌幅。
    """
    if not currency_codes:
        return []

    # 检查缓存
    cache = _load_cache()
    cache_key = ",".join(sorted(currency_codes))
    if cache_key in cache:
        entry = cache[cache_key]
        if time.time() - entry.get("ts", 0) < CACHE_TTL:
            logger.info("使用缓存的汇率数据")
            rates = []
            for r in entry.get("rates", []):
                rates.append(CurrencyRate(**r))
            return rates

    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz)
    yesterday = today - timedelta(days=1)

    # frankfurter 使用欧洲时区，需要请求前一天的数据
    # 对于周末，回退到周五
    weekday = today.weekday()
    if weekday == 0:  # 周一 → 回退到上周五
        prev_day = today - timedelta(days=3)
    elif weekday == 6:  # 周日
        prev_day = today - timedelta(days=2)
    else:
        prev_day = yesterday

    today_str = today.strftime("%Y-%m-%d")
    prev_str = prev_day.strftime("%Y-%m-%d")

    logger.info("获取汇率: %s, 对比日期: %s", today_str, prev_str)

    codes_set = set(currency_codes)

    # 获取以 USD 为基准的汇率
    latest_usd = _get_latest_rates("USD")
    prev_usd = _get_historical_rates(prev_str, "USD")

    # 获取以 CNY 为基准的汇率（或通过 USD 换算）
    # frankfurter 不直接支持 CNY 为基准，通过 USD→CNY 换算
    usd_to_cny = latest_usd.get("CNY", 7.2)
    prev_usd_to_cny = prev_usd.get("CNY", usd_to_cny)

    rates: list[CurrencyRate] = []
    updated_at = today.strftime("%Y-%m-%d %H:%M:%S") + " (UTC+8)"

    for code in currency_codes:
        name_en, name_cn = CURRENCY_NAMES.get(code, (code, code))

        # 通过 USD 计算汇率
        rate_to_usd = 1.0 / latest_usd.get(code, 1.0) if latest_usd.get(code) else 0.0
        rate_to_cny = rate_to_usd * usd_to_cny

        prev_rate_to_usd = 1.0 / prev_usd.get(code, 1.0) if prev_usd.get(code) else rate_to_usd
        prev_rate_to_cny = prev_rate_to_usd * prev_usd_to_cny

        def _change_pct(new: float, old: float) -> float:
            if old and old != 0:
                return round((new - old) / old * 100, 2)
            return 0.0

        rates.append(
            CurrencyRate(
                code=code,
                name=name_en,
                name_cn=name_cn,
                rate_to_cny=round(rate_to_cny, 4),
                rate_to_usd=round(rate_to_usd, 4),
                prev_rate_to_cny=round(prev_rate_to_cny, 4),
                prev_rate_to_usd=round(prev_rate_to_usd, 4),
                change_pct_cny=_change_pct(rate_to_cny, prev_rate_to_cny),
                change_pct_usd=_change_pct(rate_to_usd, prev_rate_to_usd),
                updated_at=updated_at,
            )
        )

    # 写入缓存
    cache[cache_key] = {
        "ts": time.time(),
        "rates": [r.__dict__ for r in rates],
    }
    _save_cache(cache)

    logger.info("成功获取 %d 个货币的汇率", len(rates))
    return rates

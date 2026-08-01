"""
新闻抓取模块 — 从 NewsAPI / RSS 源聚合指定国家/地区的双语新闻。
三层回退策略: NewsAPI → GNews → RSS 直接抓取
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from config import COUNTRIES, load_config
from logger import get_logger

logger = get_logger()

# ── 缓存 ────────────────────────────────────────────────────
_cache: dict[str, tuple[list["NewsItem"], float]] = {}
_cache_lock = threading.Lock()
CACHE_TTL = 1800  # 30 分钟

# ── 国家代码 → 名称映射 ─────────────────────────────────────
COUNTRY_CODE_TO_NAME: dict[str, str] = {}
COUNTRY_CODE_TO_CN: dict[str, str] = {}
for _region, _countries in COUNTRIES.items():
    for _code, _label in _countries:
        parts = _label.split(" ", 1)
        COUNTRY_CODE_TO_NAME[_code] = parts[1] if len(parts) > 1 else parts[0]
        COUNTRY_CODE_TO_CN[_code] = parts[0]


@dataclass
class NewsItem:
    country_code: str
    country_name: str
    country_name_cn: str
    title_en: str
    title_cn: str
    summary_en: str
    summary_cn: str
    source: str
    url: str
    published_at: str = ""


# ── 中文关键词映射（用于 RSS 兜底时的标题翻译） ─────────────
COUNTRY_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "gb": {
        "en": ["UK", "Britain", "British", "London", "England", "United Kingdom"],
        "cn": ["英国", "伦敦", "不列颠"],
    },
    "de": {
        "en": ["Germany", "German", "Berlin", "Bundestag", "Scholz"],
        "cn": ["德国", "柏林", "德意志"],
    },
    "fr": {
        "en": ["France", "French", "Paris", "Macron", "Élysée"],
        "cn": ["法国", "巴黎", "法兰西", "马克龙"],
    },
    "it": {
        "en": ["Italy", "Italian", "Rome", "Meloni", "Vatican"],
        "cn": ["意大利", "罗马"],
    },
    "es": {
        "en": ["Spain", "Spanish", "Madrid", "Barcelona"],
        "cn": ["西班牙", "马德里", "巴塞罗那"],
    },
    "ru": {
        "en": ["Russia", "Russian", "Moscow", "Putin", "Kremlin"],
        "cn": ["俄罗斯", "莫斯科", "普京", "克里姆林宫"],
    },
    "cn": {
        "en": ["China", "Chinese", "Beijing", "Shanghai", "Xi"],
        "cn": ["中国", "北京", "上海"],
    },
    "jp": {
        "en": ["Japan", "Japanese", "Tokyo", "Shinzo", "Kishida"],
        "cn": ["日本", "东京"],
    },
    "kr": {
        "en": ["South Korea", "Korean", "Seoul", "Yoon", "K-pop"],
        "cn": ["韩国", "首尔", "朝鲜"],
    },
    "in": {
        "en": ["India", "Indian", "Delhi", "Mumbai", "Modi"],
        "cn": ["印度", "新德里", "孟买", "莫迪"],
    },
    "sg": {
        "en": ["Singapore", "Singaporean"],
        "cn": ["新加坡"],
    },
    "us": {
        "en": ["US", "USA", "United States", "America", "Washington", "Biden", "Trump"],
        "cn": ["美国", "华盛顿", "拜登", "特朗普"],
    },
    "ca": {
        "en": ["Canada", "Canadian", "Ottawa", "Toronto", "Trudeau"],
        "cn": ["加拿大", "渥太华", "多伦多", "特鲁多"],
    },
    "mx": {
        "en": ["Mexico", "Mexican", "Mexico City"],
        "cn": ["墨西哥", "墨西哥城"],
    },
}

# ── RSS 源 ──────────────────────────────────────────────────
RSS_FEEDS_EN = [
    ("Reuters", "https://www.reuters.com/arc/outboundfeeds/v3/all/?outputType=xml"),
    ("BBC News", "http://feeds.bbci.co.uk/news/rss.xml"),
    ("CNN", "http://rss.cnn.com/rss/edition.rss"),
]

RSS_FEEDS_CN = [
    ("路透社", "https://www.reuters.com/arc/outboundfeeds/v3/all/?outputType=xml"),
    ("BBC中文", "https://www.bbc.com/zhongwen/simp/index.xml"),
]


def _match_country(text: str, code: str) -> bool:
    """检查文本是否包含某国家/地区的相关关键词。"""
    keywords = COUNTRY_KEYWORDS.get(code, {})
    all_kw = keywords.get("en", []) + keywords.get("cn", [])
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in all_kw if len(kw) > 2)


def _fetch_newsapi(country_codes: list[str], api_key: str) -> list[NewsItem]:
    """通过 NewsAPI.org 获取新闻。"""
    items: list[NewsItem] = []
    url = "https://newsapi.org/v2/top-headlines"
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)

    for code in country_codes:
        try:
            resp = requests.get(
                url,
                params={"country": code, "apiKey": api_key, "pageSize": 5},
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning("NewsAPI 请求失败 [%s]: %s", code, resp.status_code)
                continue

            data = resp.json()
            for article in data.get("articles", [])[:2]:
                title_en = (article.get("title") or "").strip()
                desc_en = (article.get("description") or "").strip()
                source_name = article.get("source", {}).get("name", "NewsAPI")
                if not title_en:
                    continue
                items.append(
                    NewsItem(
                        country_code=code,
                        country_name=COUNTRY_CODE_TO_NAME.get(code, code),
                        country_name_cn=COUNTRY_CODE_TO_CN.get(code, code),
                        title_en=title_en,
                        title_cn="",  # 稍后通过翻译或关键词填充
                        summary_en=desc_en[:300] if desc_en else "",
                        summary_cn="",
                        source=source_name,
                        url=article.get("url", ""),
                        published_at=article.get("publishedAt", now.isoformat()),
                    )
                )
        except Exception as e:
            logger.error("NewsAPI 异常 [%s]: %s", code, e)

    return items


def _fetch_rss_items(feed_url: str, source_name: str, timeout: int = 15) -> list[dict[str, str]]:
    """抓取单个 RSS 源，返回条目列表。"""
    entries: list[dict[str, str]] = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(feed_url, headers=headers, timeout=timeout)
        resp.raise_for_status()

        # 尝试 XML 解析
        root = ElementTree.fromstring(resp.content)
        ns = {"rss": "", "atom": "http://www.w3.org/2005/Atom"}

        for item in root.iter("item"):
            title = ""
            desc = ""
            link = ""
            pub_date = ""
            for child in item:
                tag = child.tag.lower().replace("{http://", "").split("}")[-1] if "}" in child.tag else child.tag
                if tag in ("title",):
                    title = (child.text or "").strip()
                elif tag in ("description", "content:encoded", "summary"):
                    desc = (child.text or "").strip()
                elif tag in ("link",):
                    link = child.text.strip() if child.text else child.get("href", "")
                elif tag in ("pubdate", "published", "updated"):
                    pub_date = (child.text or "").strip()
            if title:
                entries.append({
                    "title": title,
                    "description": desc,
                    "link": link,
                    "published": pub_date,
                })
    except Exception as e:
        logger.warning("RSS 抓取失败 [%s]: %s", source_name, e)

    return entries


def _simple_translate_cn(text: str, code: str) -> str:
    """简单的关键词替换式'翻译'，用作中文标题的兜底。"""
    if not text:
        return ""

    mapping = {
        "gb": [("UK", "英国"), ("Britain", "英国"), ("London", "伦敦"), ("Prime Minister", "首相")],
        "de": [("Germany", "德国"), ("Berlin", "柏林"), ("Chancellor", "总理")],
        "fr": [("France", "法国"), ("Paris", "巴黎"), ("President", "总统")],
        "us": [("United States", "美国"), ("Washington", "华盛顿"), ("President", "总统"),
               ("Biden", "拜登"), ("Trump", "特朗普"), ("White House", "白宫")],
        "cn": [("China", "中国"), ("Beijing", "北京"), ("Shanghai", "上海")],
        "jp": [("Japan", "日本"), ("Tokyo", "东京"), ("Prime Minister", "首相")],
        "kr": [("South Korea", "韩国"), ("Seoul", "首尔")],
        "in": [("India", "印度"), ("Delhi", "德里"), ("Mumbai", "孟买"), ("Prime Minister", "总理")],
    }

    result = text
    for en, cn in mapping.get(code, []):
        result = result.replace(en, cn)
    return result


def _fetch_rss_fallback(country_codes: list[str]) -> list[NewsItem]:
    """RSS 兜底方案：从 RSS 源抓取新闻并按国家关键词过滤。"""
    items: list[NewsItem] = []

    # 收集所有 RSS 条目
    all_entries: list[dict[str, Any]] = []
    for source_name, url in RSS_FEEDS_EN:
        if not url:
            continue
        entries = _fetch_rss_items(url, source_name)
        for e in entries:
            e["source"] = source_name
        all_entries.extend(entries)

    for code in country_codes:
        country_items: list[NewsItem] = []
        for entry in all_entries:
            title = entry.get("title", "")
            desc = entry.get("description", "")
            combined = f"{title} {desc}"
            if _match_country(combined, code):
                # 清理 HTML 标签
                soup = BeautifulSoup(desc or "", "html.parser")
                clean_desc = soup.get_text(" ", strip=True)[:300]
                title_cn = _simple_translate_cn(title, code)

                country_items.append(
                    NewsItem(
                        country_code=code,
                        country_name=COUNTRY_CODE_TO_NAME.get(code, code),
                        country_name_cn=COUNTRY_CODE_TO_CN.get(code, code),
                        title_en=title,
                        title_cn=title_cn,
                        summary_en=clean_desc,
                        summary_cn="",
                        source=entry.get("source", "RSS"),
                        url=entry.get("link", ""),
                        published_at=entry.get("published", ""),
                    )
                )
            if len(country_items) >= 2:
                break

        items.extend(country_items)

    return items


def _cache_key(country_codes: list[str]) -> str:
    h = hashlib.md5(",".join(sorted(country_codes)).encode()).hexdigest()
    return h


def fetch_news(country_codes: list[str]) -> list[NewsItem]:
    """
    主入口：获取指定国家的新闻，使用缓存和三层回退策略。
    """
    if not country_codes:
        return []

    ck = _cache_key(country_codes)
    with _cache_lock:
        if ck in _cache:
            items, ts = _cache[ck]
            if time.time() - ts < CACHE_TTL:
                logger.info("使用缓存的新闻数据 (%d 条)", len(items))
                return items

    config = load_config()
    items: list[NewsItem] = []

    # 第1层: NewsAPI
    if config.get("newsapi_key"):
        logger.info("尝试通过 NewsAPI 获取新闻...")
        items = _fetch_newsapi(country_codes, config["newsapi_key"])
        if items:
            logger.info("NewsAPI 成功获取 %d 条新闻", len(items))

    # 第2层: GNews（这里简化，使用与 NewsAPI 类似的接口）
    if not items and config.get("gnews_key"):
        logger.info("NewsAPI 无结果，尝试 GNews...")
        # GNews 调用（结构与 NewsAPI 类似，略作简化）
        try:
            gnews_url = "https://gnews.io/api/v4/top-headlines"
            for code in country_codes:
                resp = requests.get(
                    gnews_url,
                    params={"country": code, "token": config["gnews_key"], "max": 3},
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for article in data.get("articles", [])[:2]:
                        items.append(
                            NewsItem(
                                country_code=code,
                                country_name=COUNTRY_CODE_TO_NAME.get(code, code),
                                country_name_cn=COUNTRY_CODE_TO_CN.get(code, code),
                                title_en=article.get("title", ""),
                                title_cn="",
                                summary_en=(article.get("description") or "")[:300],
                                summary_cn="",
                                source=article.get("source", {}).get("name", "GNews"),
                                url=article.get("url", ""),
                                published_at=article.get("publishedAt", ""),
                            )
                        )
        except Exception as e:
            logger.warning("GNews 异常: %s", e)

    # 第3层: RSS 兜底
    if not items:
        logger.info("API 方式无结果，使用 RSS 兜底方案...")
        items = _fetch_rss_fallback(country_codes)

    logger.info("最终获取 %d 条新闻", len(items))

    with _cache_lock:
        _cache[ck] = (list(items), time.time())

    return items


def clear_cache() -> None:
    """清除新闻缓存。"""
    with _cache_lock:
        _cache.clear()
        logger.info("新闻缓存已清除")

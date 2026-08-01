"""
报告生成模块 — 生成双语 HTML 日报，包含今日要闻和汇率波动表格。
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from currency_fetcher import CurrencyRate
from news_fetcher import NewsItem


CSS_STYLES = """
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                 "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
    background: #f4f6f9; color: #2c3e50; line-height: 1.7;
    -webkit-text-size-adjust: 100%;
  }
  .container { max-width: 720px; margin: 0 auto; background: #ffffff; }
  .header {
    background: linear-gradient(135deg, #1a237e 0%, #283593 50%, #3949ab 100%);
    color: #fff; padding: 36px 32px 28px; text-align: center;
  }
  .header h1 { font-size: 26px; font-weight: 700; letter-spacing: 2px; margin-bottom: 6px; }
  .header .subtitle { font-size: 15px; opacity: 0.88; font-weight: 300; }
  .header .date { font-size: 13px; opacity: 0.72; margin-top: 10px; }
  .section { padding: 28px 28px 12px; }
  .section-title {
    font-size: 18px; font-weight: 700; color: #1a237e;
    border-left: 4px solid #3949ab; padding-left: 14px; margin-bottom: 18px;
    display: flex; align-items: center; gap: 10px;
  }
  .section-title .en { font-size: 13px; color: #6b7280; font-weight: 400; }
  .news-card {
    background: #fafbfc; border: 1px solid #e8ecf1; border-radius: 10px;
    padding: 18px 20px; margin-bottom: 14px;
    transition: box-shadow 0.2s;
  }
  .news-card:hover { box-shadow: 0 2px 12px rgba(26,35,126,0.08); }
  .news-card .country-tag {
    display: inline-block; background: #e8eaf6; color: #283593;
    font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 12px;
    margin-bottom: 8px; letter-spacing: 0.5px;
  }
  .news-card .title-cn { font-size: 15px; font-weight: 600; color: #1f2937; margin-bottom: 3px; }
  .news-card .title-en { font-size: 13px; color: #6b7280; margin-bottom: 8px; font-style: italic; }
  .news-card .summary-cn { font-size: 13px; color: #4b5563; margin-bottom: 4px; }
  .news-card .summary-en { font-size: 12px; color: #9ca3af; margin-bottom: 10px; }
  .news-card .meta { font-size: 11px; color: #b0b7c3; }
  .news-card .meta a { color: #3949ab; text-decoration: none; }
  table {
    width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 20px;
  }
  th {
    background: #e8eaf6; color: #1a237e; font-weight: 600; padding: 10px 8px;
    text-align: center; font-size: 12px; letter-spacing: 0.5px;
  }
  td { padding: 10px 8px; text-align: center; border-bottom: 1px solid #f0f0f0; }
  tr:hover td { background: #fafbfd; }
  .up { color: #10b981; font-weight: 600; }
  .down { color: #ef4444; font-weight: 600; }
  .flat { color: #6b7280; }
  .footer {
    background: #f9fafb; border-top: 1px solid #e5e7eb; padding: 22px 28px;
    font-size: 11px; color: #9ca3af; text-align: center; line-height: 1.8;
  }
  .footer .disclaimer { margin-bottom: 8px; }
  @media (max-width: 480px) {
    .header { padding: 24px 16px 20px; }
    .header h1 { font-size: 20px; }
    .section { padding: 16px 12px 8px; }
    .news-card { padding: 12px 14px; }
    th, td { padding: 6px 4px; font-size: 11px; }
  }
</style>
"""


def generate_html_report(
    news_items: list[NewsItem],
    currency_rates: list[CurrencyRate],
    selected_countries: Optional[list[str]] = None,
    selected_currencies: Optional[list[str]] = None,
) -> str:
    """
    生成完整的中英双语 HTML 日报。
    """
    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz)
    date_cn = today.strftime("%Y年%m月%d日")
    date_en = today.strftime("%B %d, %Y")

    html_parts: list[str] = []

    # ── 头部 ──
    html_parts.append(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日全球新闻简报 - {today.strftime('%Y-%m-%d')}</title>
{CSS_STYLES}
</head>
<body>
<div class="container">
<div class="header">
  <h1>每日全球新闻简报</h1>
  <div class="subtitle">Daily Global News Briefing</div>
  <div class="date">{date_cn} &nbsp;|&nbsp; {date_en}</div>
</div>
""")

    # ── 第一部分：今日要闻 ──
    html_parts.append("""
<div class="section">
<div class="section-title">
  <span>今日要闻</span>
  <span class="en">Top Headlines</span>
</div>
""")

    if not news_items:
        html_parts.append("""
<div class="news-card" style="text-align:center; color:#9ca3af; padding:32px;">
  <p>暂无新闻数据 | No news data available</p>
  <p style="font-size:12px; margin-top:8px;">请检查网络连接或 API 配置 | Please check network or API settings</p>
</div>
""")
    else:
        for item in news_items:
            html_parts.append(f"""
<div class="news-card">
  <span class="country-tag">{item.country_name_cn} {item.country_name}</span>
  <div class="title-cn">{item.title_cn or item.title_en}</div>
  <div class="title-en">{item.title_en}</div>
  {f'<div class="summary-cn">{item.summary_cn}</div>' if item.summary_cn else ''}
  <div class="summary-en">{item.summary_en}</div>
  <div class="meta">
    来源 Source: {item.source}
    {f' &nbsp;|&nbsp; <a href="{item.url}">阅读全文 Read more</a>' if item.url else ''}
  </div>
</div>
""")

    html_parts.append("</div>")

    # ── 第二部分：汇率波动 ──
    html_parts.append("""
<div class="section">
<div class="section-title">
  <span>汇率波动</span>
  <span class="en">Currency Fluctuations</span>
</div>
""")

    if not currency_rates:
        html_parts.append("""
<div class="news-card" style="text-align:center; color:#9ca3af; padding:32px;">
  <p>暂无汇率数据 | No exchange rate data available</p>
</div>
""")
    else:
        html_parts.append("""
<div style="overflow-x:auto;">
<table>
<thead>
<tr>
  <th>货币<br>Currency</th>
  <th>对人民币<br>CNY Rate</th>
  <th>人民币涨跌<br>CNY Δ</th>
  <th>对美元<br>USD Rate</th>
  <th>美元涨跌<br>USD Δ</th>
</tr>
</thead>
<tbody>
""")
        for r in currency_rates:
            def _arrow(pct: float) -> str:
                if pct > 0:
                    return f'<span class="up">+{pct}% &#9650;</span>'
                elif pct < 0:
                    return f'<span class="down">{pct}% &#9660;</span>'
                return '<span class="flat">0.00% &mdash;</span>'

            html_parts.append(f"""
<tr>
  <td style="text-align:left; font-weight:600;">
    {r.name_cn}<br><span style="font-size:11px;color:#9ca3af;">{r.code} {r.name}</span>
  </td>
  <td>{r.rate_to_cny:.4f}</td>
  <td>{_arrow(r.change_pct_cny)}</td>
  <td>{r.rate_to_usd:.4f}</td>
  <td>{_arrow(r.change_pct_usd)}</td>
</tr>
""")
        html_parts.append("</tbody></table></div>")
        html_parts.append(f"""
<div style="font-size:11px; color:#9ca3af; text-align:right; margin-top:-8px;">
  更新时间 Update: {currency_rates[0].updated_at if currency_rates else ''}
</div>
""")

    html_parts.append("</div>")

    # ── 页脚 ──
    html_parts.append(f"""
<div class="footer">
  <div class="disclaimer">
    <strong>免责声明 Disclaimer:</strong><br>
    本日报内容仅供参考，不构成任何投资建议。新闻内容来源于各公开媒体，版权归原作者所有。
    汇率数据仅供参考，实际交易汇率以银行柜台为准。<br>
    This briefing is for informational purposes only and does not constitute investment advice.
    News content is sourced from public media outlets. Exchange rates are indicative only.
  </div>
  <div>
    数据来源 Sources: Reuters, BBC, CNN, The Economist, NBC News, 路透社, 联合早报, CCTV &nbsp;|&nbsp;
    汇率数据 Currency: frankfurter.app (ECB)<br>
    自动生成于 Generated at: {today.strftime('%Y-%m-%d %H:%M')} (UTC+8) &nbsp;|&nbsp;
    News Daily Briefing System
  </div>
</div>
</div>
</body>
</html>
""")

    return "\n".join(html_parts)


def generate_plain_text_report(
    news_items: list[NewsItem],
    currency_rates: list[CurrencyRate],
) -> str:
    """生成纯文本版日报（兜底用）。"""
    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz)
    lines = [
        "=" * 60,
        f"  每日全球新闻简报 | Daily Global News Briefing",
        f"  {today.strftime('%Y-%m-%d %A')}",
        "=" * 60,
        "",
        "── 今日要闻 | Top Headlines ──",
        "",
    ]

    for item in news_items:
        lines.append(f"  [{item.country_name_cn}{item.country_name}] {item.title_en}")
        if item.summary_en:
            lines.append(f"     {item.summary_en[:150]}...")
        lines.append(f"     来源: {item.source}")
        lines.append("")

    lines.append("── 汇率波动 | Currency Fluctuations ──")
    lines.append("")
    lines.append(f"  {'货币':<10} {'CNY':>8} {'涨跌':>8} {'USD':>8} {'涨跌':>8}")
    lines.append("  " + "-" * 45)

    for r in currency_rates:
        arrow_cny = f"+{r.change_pct_cny}%" if r.change_pct_cny > 0 else f"{r.change_pct_cny}%"
        arrow_usd = f"+{r.change_pct_usd}%" if r.change_pct_usd > 0 else f"{r.change_pct_usd}%"
        lines.append(f"  {r.code:<10} {r.rate_to_cny:>8.4f} {arrow_cny:>8} {r.rate_to_usd:>8.4f} {arrow_usd:>8}")

    lines.append("")
    lines.append("─" * 60)
    lines.append("免责声明: 本日报内容仅供参考，不构成任何投资建议。")
    lines.append("Disclaimer: For informational purposes only.")
    return "\n".join(lines)

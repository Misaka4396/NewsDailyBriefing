"""
主程序入口 — GUI 应用，基于 tkinter + ttkbootstrap。
提供国家/货币选择、邮箱配置、日报预览/发送、定时任务管理等功能。
"""

from __future__ import annotations

import json
import os
import sys
import threading
import tkinter as tk
from datetime import datetime, timezone, timedelta
from tkinter import messagebox, ttk
from typing import Any

# 尝试导入 ttkbootstrap 以获得现代风格，失败则退回标准 ttk
try:
    import ttkbootstrap as ttkb
    from ttkbootstrap.constants import *
    HAS_BOOTSTRAP = True
except ImportError:
    HAS_BOOTSTRAP = False

from config import (
    COUNTRIES, CURRENCIES, DEFAULT_CONFIG,
    load_config, save_config,
)
from currency_fetcher import fetch_rates
from email_sender import send_daily_report, send_test_email
from logger import setup_logger, get_logger
from news_fetcher import fetch_news, clear_cache
from report_generator import generate_html_report
from scheduler import DailyScheduler
from tray_manager import TrayManager

# ── 初始化 logger ──
logger = get_logger()
if not logger.handlers:
    setup_logger()


# ── 常量 ──
APP_TITLE = "全球每日新闻日报推送器"
APP_SUBTITLE = "Daily Global News Briefing System"
WINDOW_WIDTH = 950
WINDOW_HEIGHT = 720
BEIJING_TZ = timezone(timedelta(hours=8))


# ── 自定义日志处理器（桥接到 GUI） ──
class GuiLogHandler:
    """将日志消息转发到 GUI 日志窗口。"""

    def __init__(self) -> None:
        self._callback: Any = None

    def set_callback(self, cb: Any) -> None:
        self._callback = cb

    def emit(self, message: str) -> None:
        if self._callback:
            try:
                self._callback(message)
            except Exception:
                pass


gui_log_handler = GuiLogHandler()


class App:
    """主应用类。"""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(780, 600)

        # 防止误关闭，改为最小化到托盘
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 状态变量
        self._running_task = False
        self._country_vars: dict[str, tk.BooleanVar] = {}
        self._currency_vars: dict[str, tk.BooleanVar] = {}
        self._preview_content: str = ""
        self._preview_window: tk.Toplevel | None = None

        # 调度器
        self._scheduler = DailyScheduler()

        # 系统托盘
        self._tray = TrayManager(
            on_show=self._show_window,
            on_generate=self._generate_and_send,
            on_exit=self._quit_app,
        )

        # 加载配置
        self._config = load_config()

        self._build_ui()
        self._load_config_to_ui()

        # 启动调度器
        self._start_scheduler()

        # 日志
        logger.info("应用已启动")

    # ── UI 构建 ────────────────────────────────────────────

    def _build_ui(self) -> None:
        """构建完整 UI。"""
        # 外层容器
        outer = ttk.Frame(self.root, padding=4)
        outer.pack(fill=tk.BOTH, expand=True)

        # 标题栏
        title_frame = ttk.Frame(outer)
        title_frame.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(
            title_frame, text=APP_TITLE,
            font=("Microsoft YaHei", 16, "bold"),
        ).pack(side=tk.LEFT, padx=4)
        ttk.Label(
            title_frame, text=APP_SUBTITLE,
            font=("Segoe UI", 10), foreground="gray",
        ).pack(side=tk.LEFT, padx=8)
        # 调度器状态
        self._scheduler_status_label = ttk.Label(
            title_frame, text="", font=("Microsoft YaHei", 9), foreground="#3949ab",
        )
        self._scheduler_status_label.pack(side=tk.RIGHT, padx=8)

        # 创建 Notebook（选项卡布局）
        nb = ttk.Notebook(outer)
        nb.pack(fill=tk.BOTH, expand=True, pady=2)

        # 选项卡 1: 主要设置
        tab_main = ttk.Frame(nb)
        nb.add(tab_main, text="  📋 设置 Settings  ")

        # 选项卡 2: 日志 & 预览
        tab_log = ttk.Frame(nb)
        nb.add(tab_log, text="  📄 日志 & 预览 Log & Preview  ")

        # 选项卡 3: 关于
        tab_about = ttk.Frame(nb)
        nb.add(tab_about, text="  ℹ️ 关于 About  ")

        self._build_settings_tab(tab_main)
        self._build_log_tab(tab_log)
        self._build_about_tab(tab_about)

        # 状态栏
        status_frame = ttk.Frame(outer, relief=tk.SUNKEN if not HAS_BOOTSTRAP else tk.FLAT)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(4, 0))
        self._status_var = tk.StringVar(value="就绪 Ready")
        ttk.Label(
            status_frame, textvariable=self._status_var,
            font=("Microsoft YaHei", 9), foreground="gray",
        ).pack(side=tk.LEFT, padx=6, pady=2)
        ttk.Label(
            status_frame,
            text=f"下次运行: {self._scheduler.get_next_run_time()}",
            font=("Microsoft YaHei", 8), foreground="#9ca3af",
        ).pack(side=tk.RIGHT, padx=6, pady=2)

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        """构建设置选项卡。"""
        # 使用 Canvas + Scrollbar 实现滚动
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", tags="inner")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 鼠标滚轮支持（仅当鼠标在 Canvas 上时生效）
        def _on_mousewheel(event: Any) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        def _bind_wheel(_e: Any = None) -> None:
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_wheel(_e: Any = None) -> None:
            canvas.unbind_all("<MouseWheel>")
        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)

        # ── 国家选择 ──
        country_frame = ttk.LabelFrame(scroll_frame, text="🌍 国家选择 | Country Selection", padding=10)
        country_frame.pack(fill=tk.X, padx=8, pady=6)

        self._country_cb_frames: dict[str, ttk.Frame] = {}
        for region_name, countries in COUNTRIES.items():
            region_frame = ttk.LabelFrame(country_frame, text=region_name, padding=6)
            region_frame.pack(fill=tk.X, padx=4, pady=3)

            inner = ttk.Frame(region_frame)
            inner.pack(fill=tk.X)

            for code, label in countries:
                var = tk.BooleanVar(value=code in self._config.get("countries", []))
                self._country_vars[code] = var
                cb = ttk.Checkbutton(inner, text=label, variable=var)
                cb.pack(side=tk.LEFT, padx=6, pady=2)

        # ── 货币选择 ──
        currency_frame = ttk.LabelFrame(scroll_frame, text="💱 货币选择 | Currency Selection", padding=10)
        currency_frame.pack(fill=tk.X, padx=8, pady=6)

        curr_inner = ttk.Frame(currency_frame)
        curr_inner.pack(fill=tk.X)

        for code, name in CURRENCIES:
            var = tk.BooleanVar(value=code in self._config.get("currencies", []))
            self._currency_vars[code] = var
            cb = ttk.Checkbutton(curr_inner, text=f"{code} - {name}", variable=var)
            cb.pack(side=tk.LEFT, padx=4, pady=2)

        # ── 邮箱设置 ──
        mail_frame = ttk.LabelFrame(scroll_frame, text="📧 邮箱设置 | Email Settings", padding=10)
        mail_frame.pack(fill=tk.X, padx=8, pady=6)

        # 收件人
        row1 = ttk.Frame(mail_frame)
        row1.pack(fill=tk.X, pady=3)
        ttk.Label(row1, text="收件人 To:", width=14).pack(side=tk.LEFT)
        self._recipient_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self._recipient_var, width=50).pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)

        # SMTP 服务器
        row2 = ttk.Frame(mail_frame)
        row2.pack(fill=tk.X, pady=3)
        ttk.Label(row2, text="SMTP 服务器:", width=14).pack(side=tk.LEFT)
        self._smtp_server_var = tk.StringVar(value="smtp.gmail.com")
        ttk.Entry(row2, textvariable=self._smtp_server_var, width=28).pack(side=tk.LEFT, padx=4)
        ttk.Label(row2, text="端口 Port:").pack(side=tk.LEFT, padx=(8, 4))
        self._smtp_port_var = tk.StringVar(value="587")
        ttk.Entry(row2, textvariable=self._smtp_port_var, width=7).pack(side=tk.LEFT)

        # TLS/SSL
        row2b = ttk.Frame(mail_frame)
        row2b.pack(fill=tk.X, pady=3)
        ttk.Label(row2b, text="", width=14).pack(side=tk.LEFT)
        self._smtp_tls_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2b, text="使用 TLS (端口 587)", variable=self._smtp_tls_var).pack(side=tk.LEFT)
        ttk.Label(
            row2b,
            text="  |  Gmail 587+TLS | QQ 587+TLS | 163 465 关TLS | Outlook 587+TLS",
            font=("Microsoft YaHei", 8), foreground="#9ca3af",
        ).pack(side=tk.LEFT, padx=8)

        # 发件人
        row3 = ttk.Frame(mail_frame)
        row3.pack(fill=tk.X, pady=3)
        ttk.Label(row3, text="发件人 From:", width=14).pack(side=tk.LEFT)
        self._sender_email_var = tk.StringVar()
        ttk.Entry(row3, textvariable=self._sender_email_var, width=50).pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)

        # 授权码
        row4 = ttk.Frame(mail_frame)
        row4.pack(fill=tk.X, pady=3)
        ttk.Label(row4, text="授权码 Password:", width=14).pack(side=tk.LEFT)
        self._sender_password_var = tk.StringVar()
        ttk.Entry(row4, textvariable=self._sender_password_var, width=50, show="*").pack(
            side=tk.LEFT, padx=4, fill=tk.X, expand=True
        )

        # API Key
        api_frame = ttk.LabelFrame(scroll_frame, text="🔑 API 密钥 (可选) | API Keys (Optional)", padding=10)
        api_frame.pack(fill=tk.X, padx=8, pady=6)

        row5 = ttk.Frame(api_frame)
        row5.pack(fill=tk.X, pady=3)
        ttk.Label(row5, text="NewsAPI Key:", width=14).pack(side=tk.LEFT)
        self._newsapi_var = tk.StringVar()
        ttk.Entry(row5, textvariable=self._newsapi_var, width=50, show="*").pack(
            side=tk.LEFT, padx=4, fill=tk.X, expand=True
        )
        ttk.Label(
            row5, text="免费申请: newsapi.org",
            font=("Microsoft YaHei", 8), foreground="#9ca3af",
        ).pack(side=tk.LEFT, padx=4)

        row6 = ttk.Frame(api_frame)
        row6.pack(fill=tk.X, pady=3)
        ttk.Label(row6, text="GNews Key:", width=14).pack(side=tk.LEFT)
        self._gnews_var = tk.StringVar()
        ttk.Entry(row6, textvariable=self._gnews_var, width=50, show="*").pack(
            side=tk.LEFT, padx=4, fill=tk.X, expand=True
        )
        ttk.Label(
            row6, text="免费申请: gnews.io",
            font=("Microsoft YaHei", 8), foreground="#9ca3af",
        ).pack(side=tk.LEFT, padx=4)

        # ── 操作按钮 ──
        btn_frame = ttk.Frame(scroll_frame)
        btn_frame.pack(fill=tk.X, padx=8, pady=10)

        self._btn_generate_send = ttk.Button(
            btn_frame, text="🚀 立即生成并发送日报 | Generate & Send",
            command=self._generate_and_send,
        )
        self._btn_generate_send.pack(side=tk.LEFT, padx=4, ipadx=8, ipady=4)

        self._btn_preview = ttk.Button(
            btn_frame, text="📋 仅生成本地预览 | Preview Only",
            command=self._generate_preview,
        )
        self._btn_preview.pack(side=tk.LEFT, padx=4, ipadx=8, ipady=4)

        self._btn_test_email = ttk.Button(
            btn_frame, text="✉️ 发送测试邮件 | Test Email",
            command=self._send_test_email,
        )
        self._btn_test_email.pack(side=tk.LEFT, padx=4, ipadx=8, ipady=4)

        self._btn_save = ttk.Button(
            btn_frame, text="💾 保存配置 | Save Config",
            command=self._save_config_from_ui,
        )
        self._btn_save.pack(side=tk.RIGHT, padx=4, ipadx=8, ipady=4)

        # 进度条
        self._progress = ttk.Progressbar(scroll_frame, mode="indeterminate")

    def _build_log_tab(self, parent: ttk.Frame) -> None:
        """构建日志与预览选项卡。"""
        # 上半部分：日志
        log_frame = ttk.LabelFrame(parent, text="📝 操作日志 | Operation Log", padding=6)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

        self._log_text = tk.Text(
            log_frame, wrap=tk.WORD, state=tk.DISABLED,
            font=("Consolas", 9), bg="#1e1e2e", fg="#cdd6f4",
            insertbackground="white", relief=tk.FLAT,
        )
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_scroll.set)
        self._log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 清除按钮
        log_btn_frame = ttk.Frame(log_frame)
        log_btn_frame.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(log_btn_frame, text="清除日志 Clear", command=self._clear_log).pack(side=tk.RIGHT, padx=4)
        ttk.Label(
            log_btn_frame, text="日志自动保存到 logs/news_daily.log",
            font=("Microsoft YaHei", 8), foreground="#9ca3af",
        ).pack(side=tk.LEFT)

        # 下半部分：预览区域
        preview_frame = ttk.LabelFrame(parent, text="📰 日报预览 | Report Preview", padding=6)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 8))

        # 使用简单的 Text 显示 HTML 源码摘要（Tkinter 不支持直接渲染 HTML）
        self._preview_text = tk.Text(
            preview_frame, wrap=tk.WORD, state=tk.DISABLED,
            font=("Microsoft YaHei", 10), bg="#ffffff", fg="#1f2937",
        )
        preview_scroll = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self._preview_text.yview)
        self._preview_text.configure(yscrollcommand=preview_scroll.set)
        self._preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        preview_btn_frame = ttk.Frame(preview_frame)
        preview_btn_frame.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(
            preview_btn_frame, text="💾 保存为 HTML | Save as HTML",
            command=self._save_preview_html,
        ).pack(side=tk.RIGHT, padx=4)
        ttk.Button(
            preview_btn_frame, text="🌐 在浏览器打开 | Open in Browser",
            command=self._open_in_browser,
        ).pack(side=tk.RIGHT, padx=4)

    def _build_about_tab(self, parent: ttk.Frame) -> None:
        """构建关于选项卡。"""
        about_frame = ttk.Frame(parent, padding=30)
        about_frame.pack(expand=True)

        lines = [
            (APP_TITLE, ("Microsoft YaHei", 18, "bold")),
            (APP_SUBTITLE, ("Segoe UI", 12)),
            ("", ("", 10)),
            ("功能特性 Features:", ("Microsoft YaHei", 12, "bold")),
            ("  • 多国新闻聚合，中英双语显示", ("Microsoft YaHei", 10)),
            ("  • 实时汇率查询与涨跌分析", ("Microsoft YaHei", 10)),
            ("  • HTML 精美日报邮件推送", ("Microsoft YaHei", 10)),
            ("  • 每日北京时间 8:00 自动发送", ("Microsoft YaHei", 10)),
            ("  • 系统托盘后台运行", ("Microsoft YaHei", 10)),
            ("", ("", 6)),
            ("数据来源 Sources:", ("Microsoft YaHei", 12, "bold")),
            ("  • 新闻: Reuters, BBC, CNN, NBC News, 路透社, 联合早报, CCTV", ("Microsoft YaHei", 10)),
            ("  • 汇率: frankfurter.app (欧洲央行 ECB 数据)", ("Microsoft YaHei", 10)),
            ("  • API: NewsAPI.org / GNews.io (可选)", ("Microsoft YaHei", 10)),
            ("", ("", 6)),
            ("技术栈 Tech Stack:", ("Microsoft YaHei", 12, "bold")),
            ("  • Python 3.11+ / Tkinter / ttkbootstrap", ("Microsoft YaHei", 10)),
            ("  • schedule / pystray / Pillow", ("Microsoft YaHei", 10)),
            ("  • cryptography / requests / BeautifulSoup4", ("Microsoft YaHei", 10)),
            ("", ("", 6)),
            ("📧 配置邮箱 | Email Setup Guide:", ("Microsoft YaHei", 11, "bold")),
            ("  • Gmail: smtp.gmail.com:587 TLS → 需开启App Password", ("Microsoft YaHei", 9)),
            ("  • QQ邮箱: smtp.qq.com:587 TLS → 需生成授权码", ("Microsoft YaHei", 9)),
            ("  • 163邮箱: smtp.163.com:465 SSL → 需开启SMTP服务", ("Microsoft YaHei", 9)),
            ("  • Outlook: smtp-mail.outlook.com:587 TLS → 需用账户密码", ("Microsoft YaHei", 9)),
            ("  • Office365: smtp.office365.com:587 TLS → 需用企业账户", ("Microsoft YaHei", 9)),
        ]

        for i, (text, font_spec) in enumerate(lines):
            if not text:
                ttk.Frame(about_frame, height=6).pack()
                continue
            fg = "#1a237e" if "bold" in str(font_spec) else "#4b5563"
            lbl = ttk.Label(about_frame, text=text, font=font_spec)
            lbl.pack(anchor=tk.W, pady=1)

    # ── 配置操作 ──────────────────────────────────────────

    def _load_config_to_ui(self) -> None:
        """将配置加载到 UI 控件。"""
        cfg = self._config

        for code, var in self._country_vars.items():
            var.set(code in cfg.get("countries", []))

        for code, var in self._currency_vars.items():
            var.set(code in cfg.get("currencies", []))

        self._recipient_var.set(cfg.get("recipient_email", ""))
        self._smtp_server_var.set(cfg.get("smtp_server", "smtp.gmail.com"))
        self._smtp_port_var.set(str(cfg.get("smtp_port", 587)))
        self._smtp_tls_var.set(cfg.get("smtp_use_tls", True))
        self._sender_email_var.set(cfg.get("sender_email", ""))
        self._sender_password_var.set(cfg.get("sender_password", ""))
        self._newsapi_var.set(cfg.get("newsapi_key", ""))
        self._gnews_var.set(cfg.get("gnews_key", ""))

    def _save_config_from_ui(self) -> None:
        """从 UI 收集配置并保存。"""
        cfg = {
            "countries": [code for code, var in self._country_vars.items() if var.get()],
            "currencies": [code for code, var in self._currency_vars.items() if var.get()],
            "recipient_email": self._recipient_var.get().strip(),
            "smtp_server": self._smtp_server_var.get().strip(),
            "smtp_port": int(self._smtp_port_var.get() or "587"),
            "smtp_use_tls": self._smtp_tls_var.get(),
            "sender_email": self._sender_email_var.get().strip(),
            "sender_password": self._sender_password_var.get().strip(),
            "newsapi_key": self._newsapi_var.get().strip(),
            "gnews_key": self._gnews_var.get().strip(),
        }

        if save_config(cfg):
            self._config = cfg
            self._set_status("配置已保存 | Config saved")
            self._log("✅ 配置保存成功")
        else:
            self._set_status("保存配置失败 | Save failed")
            messagebox.showerror("错误 Error", "保存配置失败，请查看日志")

    # ── 核心操作 ──────────────────────────────────────────

    def _get_selected_countries(self) -> list[str]:
        return [code for code, var in self._country_vars.items() if var.get()]

    def _get_selected_currencies(self) -> list[str]:
        return [code for code, var in self._currency_vars.items() if var.get()]

    def _generate_and_send(self) -> None:
        """后台线程：生成日报并发送邮件。"""
        if self._running_task:
            messagebox.showinfo("提示 Info", "任务正在执行中，请稍候...\nTask is running, please wait...")
            return
        self._start_task()
        threading.Thread(target=self._do_generate_and_send, daemon=True).start()

    def _do_generate_and_send(self) -> None:
        """生成日报并发送（在后台线程运行）。"""
        try:
            countries = self._get_selected_countries()
            currencies = self._get_selected_currencies()

            if not countries:
                self._log("⚠️ 未选择任何国家，将获取所有可用区域的新闻")
            if not currencies:
                self._log("⚠️ 未选择任何货币")

            self._log("=" * 50)
            self._log(f"⏰ 开始生成日报 [{datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M')}]")

            # 获取新闻
            self._log("📡 正在获取新闻...")
            news_items = fetch_news(countries)
            self._log(f"📡 获取到 {len(news_items)} 条新闻")

            # 获取汇率
            self._log("💱 正在获取汇率数据...")
            currency_rates = fetch_rates(currencies)
            self._log(f"💱 获取到 {len(currency_rates)} 个货币的汇率")

            # 生成 HTML
            self._log("📝 正在生成日报...")
            html = generate_html_report(news_items, currency_rates)
            self._preview_content = html

            # 更新预览
            self.root.after(0, lambda: self._update_preview(html))

            # 发送邮件
            self._log("📧 正在发送邮件...")
            ok, msg = send_daily_report(html, self._config)

            if ok:
                self._log(f"✅ {msg}")
                self.root.after(0, lambda: self._set_status("日报已发送 | Report sent ✅"))
            else:
                self._log(f"❌ {msg}")
                self.root.after(0, lambda: self._set_status(f"发送失败: {msg}"))
                self.root.after(0, lambda: messagebox.showerror("发送失败 Send Failed", msg))

        except Exception as e:
            self._log(f"❌ 生成日报异常: {e}")
            logger.exception("生成日报异常")
            self.root.after(0, lambda: messagebox.showerror("错误 Error", str(e)))
        finally:
            self._end_task()

    def _generate_preview(self) -> None:
        """后台线程：仅生成本地预览。"""
        if self._running_task:
            messagebox.showinfo("提示 Info", "任务正在执行中...")
            return
        self._start_task()
        threading.Thread(target=self._do_generate_preview, daemon=True).start()

    def _do_generate_preview(self) -> None:
        """生成预览（在后台线程运行）。"""
        try:
            countries = self._get_selected_countries()
            currencies = self._get_selected_currencies()

            self._log("=" * 50)
            self._log(f"⏰ 开始生成预览 [{datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M')}]")

            self._log("📡 正在获取新闻...")
            news_items = fetch_news(countries)
            self._log(f"📡 获取到 {len(news_items)} 条新闻")

            self._log("💱 正在获取汇率数据...")
            currency_rates = fetch_rates(currencies)
            self._log(f"💱 获取到 {len(currency_rates)} 个货币的汇率")

            self._log("📝 正在生成日报 HTML...")
            html = generate_html_report(news_items, currency_rates)
            self._preview_content = html

            self.root.after(0, lambda: self._update_preview(html))
            self._log("✅ 预览已生成（见下方预览区）")
            self.root.after(0, lambda: self._set_status("预览已生成 | Preview ready ✅"))

        except Exception as e:
            self._log(f"❌ 生成预览异常: {e}")
            logger.exception("生成预览异常")
        finally:
            self._end_task()

    def _send_test_email(self) -> None:
        """发送测试邮件。"""
        self._save_config_from_ui()  # 先保存最新配置
        self._start_task()
        threading.Thread(target=self._do_send_test_email, daemon=True).start()

    def _do_send_test_email(self) -> None:
        """发送测试邮件（后台线程）。"""
        try:
            self._log("✉️ 正在发送测试邮件...")
            ok, msg = send_test_email(self._config)
            if ok:
                self._log(f"✅ {msg}")
                self.root.after(0, lambda: self._set_status("测试邮件已发送 | Test email sent ✅"))
                self.root.after(0, lambda: messagebox.showinfo("成功 Success", msg))
            else:
                self._log(f"❌ {msg}")
                self.root.after(0, lambda: self._set_status(f"测试失败: {msg}"))
                self.root.after(0, lambda: messagebox.showerror("失败 Failed", msg))
        except Exception as e:
            self._log(f"❌ 发送异常: {e}")
        finally:
            self._end_task()

    # ── 调度器 ────────────────────────────────────────────

    def _start_scheduler(self) -> None:
        """启动每日定时任务。"""
        self._scheduler.start(task=self._on_scheduled_trigger)
        next_run = self._scheduler.get_next_run_time()
        self._scheduler_status_label.configure(text=f"⏰ 定时任务已开启 | 下次: {next_run}")
        self._log(f"⏰ 定时任务已开启，每日北京时间 8:00 自动发送")

    def _on_scheduled_trigger(self) -> None:
        """定时任务触发（在调度器线程中调用）。"""
        self._log("⏰ 定时任务触发，开始自动生成并发送日报...")
        self._do_generate_and_send()
        # 更新下次运行时间
        self.root.after(0, lambda: self._scheduler_status_label.configure(
            text=f"⏰ 定时任务已开启 | 下次: {self._scheduler.get_next_run_time()}"
        ))

    # ── 辅助方法 ──────────────────────────────────────────

    def _start_task(self) -> None:
        """标记任务开始，禁用按钮，显示进度条。"""
        self._running_task = True
        self.root.after(0, lambda: self._set_buttons_state(tk.DISABLED))
        self.root.after(0, lambda: self._progress.pack(fill=tk.X, padx=8, pady=(0, 6)))
        self.root.after(0, lambda: self._progress.start(10))

    def _end_task(self) -> None:
        """标记任务结束，恢复按钮。"""
        self._running_task = False
        self.root.after(0, lambda: self._progress.stop())
        self.root.after(0, lambda: self._progress.pack_forget())
        self.root.after(0, lambda: self._set_buttons_state(tk.NORMAL))

    def _set_buttons_state(self, state: str) -> None:
        for btn in [self._btn_generate_send, self._btn_preview, self._btn_test_email]:
            try:
                btn.configure(state=state)
            except Exception:
                pass

    def _set_status(self, text: str) -> None:
        """更新状态栏。"""
        try:
            self._status_var.set(text)
        except Exception:
            pass

    def _log(self, message: str) -> None:
        """向 GUI 日志窗口追加消息。"""
        ts = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{ts}] {message}\n"
        try:
            self._log_text.configure(state=tk.NORMAL)
            self._log_text.insert(tk.END, full_msg)
            self._log_text.see(tk.END)
            self._log_text.configure(state=tk.DISABLED)
        except Exception:
            pass
        logger.info(message)

    def _clear_log(self) -> None:
        """清除日志窗口。"""
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        self._log_text.configure(state=tk.DISABLED)

    def _update_preview(self, html: str) -> None:
        """更新预览区域（显示纯文本摘要）。"""
        # Tkinter 不支持直接渲染 HTML，显示文本摘要
        import re
        clean = re.sub(r"<[^>]+>", "", html)
        clean = re.sub(r"\n{3,}", "\n\n", clean).strip()

        self._preview_text.configure(state=tk.NORMAL)
        self._preview_text.delete("1.0", tk.END)
        # 显示前 8000 字符
        self._preview_text.insert(tk.END, clean[:8000])
        if len(clean) > 8000:
            self._preview_text.insert(tk.END, "\n\n... (内容过长，已截断 | Content truncated)")
        self._preview_text.configure(state=tk.DISABLED)

    def _save_preview_html(self) -> None:
        """将预览内容保存为 HTML 文件。"""
        if not self._preview_content:
            messagebox.showwarning("警告 Warning", "请先生成预览")
            return
        try:
            date_str = datetime.now(BEIJING_TZ).strftime("%Y%m%d")
            filename = f"news_daily_{date_str}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(self._preview_content)
            self._log(f"💾 日报已保存为: {filename}")
            self._set_status(f"已保存: {filename}")
            messagebox.showinfo("保存成功 Saved", f"日报已保存到:\n{os.path.abspath(filename)}")
        except Exception as e:
            messagebox.showerror("保存失败 Save Failed", str(e))

    def _open_in_browser(self) -> None:
        """在浏览器中打开预览。"""
        if not self._preview_content:
            messagebox.showwarning("警告 Warning", "请先生成预览")
            return
        try:
            import tempfile
            import webbrowser
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".html", delete=False, encoding="utf-8"
            ) as f:
                f.write(self._preview_content)
                tmp_path = f.name
            webbrowser.open(f"file:///{tmp_path}")
            self._log(f"🌐 已在浏览器中打开预览")
        except Exception as e:
            messagebox.showerror("打开失败 Open Failed", str(e))

    # ── 窗口管理 ──────────────────────────────────────────

    def _on_close(self) -> None:
        """关闭窗口 → 最小化到系统托盘。"""
        self.root.withdraw()
        try:
            self._tray.start()
        except Exception as e:
            logger.warning("启动托盘失败: %s", e)
        self._log("📌 应用已最小化到系统托盘 | Minimized to tray")

    def _show_window(self) -> None:
        """从托盘恢复主窗口。"""
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)
        self._log("📋 主窗口已恢复")

    def _quit_app(self) -> None:
        """完全退出应用。"""
        self._scheduler.stop()
        try:
            self._tray.stop()
        except Exception:
            pass
        self._log("👋 应用已退出")
        self.root.after(0, self.root.destroy)


# ── 入口 ────────────────────────────────────────────────────

def main() -> None:
    """应用入口。"""
    setup_logger()

    if HAS_BOOTSTRAP:
        root = ttkb.Window(themename="flatly")
    else:
        root = tk.Tk()

    # 设置样式
    style = ttk.Style()
    if "flatly" not in style.theme_names():
        try:
            style.theme_use("clam")  # clam 比默认好看
        except Exception:
            pass

    app = App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

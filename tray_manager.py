"""
系统托盘模块 — 支持最小化到系统托盘，后台运行。
右键菜单：显示主窗口 / 立即生成日报 / 退出。
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from PIL import Image, ImageDraw
import pystray

from logger import get_logger

logger = get_logger()


def _create_tray_icon_image(size: int = 64) -> Image.Image:
    """生成应用图标（蓝色圆形 + N 字样）。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 蓝色圆形背景
    margin = 2
    draw.ellipse([margin, margin, size - margin, size - margin], fill=(26, 35, 126, 255))

    # 白色 "N" 字样
    import textwrap
    draw.text(
        (size // 2, size // 2),
        "N",
        fill=(255, 255, 255, 255),
        anchor="mm",
    )
    return img


class TrayManager:
    """系统托盘管理器。"""

    def __init__(
        self,
        on_show: Callable[[], None],
        on_generate: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self._on_show = on_show
        self._on_generate = on_generate
        self._on_exit = on_exit
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """在独立线程中启动托盘图标。"""
        if self._icon is not None:
            return

        image = _create_tray_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("📋 显示主窗口 Show", self._on_show, default=True),
            pystray.MenuItem("📨 立即生成日报 Generate Now", self._on_generate),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ 退出 Exit", self._on_quit),
        )
        self._icon = pystray.Icon(
            "news_daily",
            image,
            "全球每日新闻日报推送器",
            menu,
        )

        self._thread = threading.Thread(target=self._icon.run, daemon=True, name="tray")
        self._thread.start()
        logger.info("系统托盘已启动")

    def stop(self) -> None:
        """停止托盘图标。"""
        if self._icon is not None:
            self._icon.stop()
            self._icon = None
            logger.info("系统托盘已停止")

    def _on_quit(self) -> None:
        """托盘菜单退出。"""
        self.stop()
        self._on_exit()

"""
定时任务模块 — 每天北京时间 8:00 自动生成并发送日报。
使用 schedule 库实现，在独立线程中运行。
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional

import schedule

from logger import get_logger

logger = get_logger()

BEIJING_TZ = timezone(timedelta(hours=8))
TARGET_HOUR = 8
TARGET_MINUTE = 0


class DailyScheduler:
    """每天在指定北京时间执行任务的调度器。"""

    def __init__(self) -> None:
        self._task: Optional[Callable[[], None]] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, task: Callable[[], None]) -> None:
        """启动调度器，每天早 8 点执行 task。"""
        if self._running:
            logger.warning("调度器已在运行")
            return

        self._task = task
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="scheduler")
        self._thread.start()
        logger.info("调度器已启动，每日北京时间 %02d:%02d 执行任务", TARGET_HOUR, TARGET_MINUTE)

    def stop(self) -> None:
        """停止调度器。"""
        if not self._running:
            return
        self._stop_event.set()
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        logger.info("调度器已停止")

    def _run(self) -> None:
        # 设置 schedule 任务
        schedule.every().day.at(f"{TARGET_HOUR:02d}:{TARGET_MINUTE:02d}").do(self._execute)

        while not self._stop_event.is_set():
            schedule.run_pending()
            # 每 30 秒检查一次
            for _ in range(30):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def _execute(self) -> None:
        """执行任务并记录日志。"""
        now = datetime.now(BEIJING_TZ)
        logger.info("══════ 定时任务触发 [%s] ══════", now.strftime("%Y-%m-%d %H:%M:%S"))
        try:
            if self._task:
                self._task()
        except Exception as e:
            logger.error("定时任务执行异常: %s", e)
        logger.info("══════ 定时任务结束 ══════")

    def get_next_run_time(self) -> str:
        """获取下次运行时间描述。"""
        now = datetime.now(BEIJING_TZ)
        next_run = now.replace(hour=TARGET_HOUR, minute=TARGET_MINUTE, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run.strftime("%Y-%m-%d %H:%M") + " (UTC+8)"

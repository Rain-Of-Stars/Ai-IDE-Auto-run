# -*- coding: utf-8 -*-
"""
自适应扫描调度器：根据事件与命中/未命中动态调整下一次扫描延时。

设计要点：
- 命中后进入冷却：使用配置项 hit_cooldown_ms；
- 未命中采用指数退避：active_scan_interval_ms * 2^miss_count，封顶 miss_backoff_ms_max；
- 前台非白名单进程时进入空闲扫描：idle_scan_interval_ms；
- 支持 scan_mode：'event' 使用白名单驱动；'polling' 忽略白名单始终积极扫描。
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import List


@dataclass
class SchedulerConfig:
    """调度相关配置（从AppConfig映射）。"""
    scan_mode: str = "event"  # 'event' 或 'polling'
    active_scan_interval_ms: int = 120
    idle_scan_interval_ms: int = 2000
    miss_backoff_ms_max: int = 5000
    hit_cooldown_ms: int = 4000
    process_whitelist: List[str] = field(default_factory=lambda: ["Code.exe", "Windsurf.exe", "Trae.exe"])


class AdaptiveScanScheduler:
    """自适应扫描调度器。"""

    def __init__(self, cfg: SchedulerConfig):
        # 运行状态
        self.active: bool = False  # 是否处于积极扫描态
        self.miss_count: int = 0   # 连续未命中计数
        self.last_hit_ts: float = 0.0  # 上次命中时间戳
        self.last_foreground: str = ""  # 最近一次前台进程名
        # 配置
        self.cfg = cfg

    # ---------- 事件输入 ----------

    def on_hit(self) -> None:
        """命中事件：重置退避并进入命中冷却。"""
        self.miss_count = 0
        self.last_hit_ts = time.monotonic()

    def on_miss(self) -> None:
        """未命中事件：累加退避计数。"""
        # 在冷却区间内的 miss 不累加，避免放大退避
        if not self._in_hit_cooldown():
            self.miss_count += 1

    def on_foreground_change(self, process_name: str | None) -> None:
        """前台进程变化：更新 active 状态。
        - event 模式：白名单内 active=True，否则 False；
        - polling 模式：忽略白名单，始终 active=True。
        """
        self.last_foreground = (process_name or "").strip()
        mode = (self.cfg.scan_mode or "event").lower()
        if mode == "polling":
            self.active = True
            return
        # event 模式：白名单判断
        pn = self.last_foreground.lower()
        wl = [s.lower() for s in (self.cfg.process_whitelist or [])]
        self.active = (pn in wl) if pn else False

    # ---------- 输出：下一次扫描延时 ----------

    def next_delay_ms(self) -> int:
        """计算下一次扫描延时（毫秒）。"""
        # 命中冷却：优先返回剩余冷却时间
        if self._in_hit_cooldown():
            remaining = int(self._hit_remaining_ms())
            return max(1, remaining)

        # 非 active：空闲扫描间隔
        if not self.active:
            return max(1, int(self.cfg.idle_scan_interval_ms))

        # active：指数退避
        base = max(1, int(self.cfg.active_scan_interval_ms))
        # 指数退避，封顶
        delay = base * (1 << min(self.miss_count, 16))
        delay = min(int(self.cfg.miss_backoff_ms_max), delay)
        return max(base, delay)

    # ---------- 内部工具 ----------

    def _in_hit_cooldown(self) -> bool:
        return (time.monotonic() - self.last_hit_ts) * 1000.0 < float(self.cfg.hit_cooldown_ms)

    def _hit_remaining_ms(self) -> float:
        elapsed_ms = (time.monotonic() - self.last_hit_ts) * 1000.0
        return max(0.0, float(self.cfg.hit_cooldown_ms) - elapsed_ms)


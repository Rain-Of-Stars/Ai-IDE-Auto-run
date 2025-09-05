# -*- coding: utf-8 -*-
"""
有界“最新帧优先”队列

设计目标：
- 队列长度上限为2，生产者放入新帧时若已满则丢弃最旧帧；
- 消费者每次仅取“当前最新的一帧”，避免排队导致延迟累积；
- 线程安全，尽量减少锁竞争；
- 仅在内存中流转数据，不涉及任何磁盘写入。
"""
from __future__ import annotations
import threading
from collections import deque
from typing import Optional, Tuple


class BoundedLatestQueue:
    """长度≤2的最新帧队列，始终优先保留最新帧。

    典型用法：
    - 生产者：`put(frame)`；
    - 消费者：`get_latest()`，返回(是否获取成功, 帧对象)。
    """

    def __init__(self, maxlen: int = 2):
        # 队列长度限制，强制≥1且≤2（防御性约束）
        self._maxlen = max(1, min(int(maxlen), 2))
        self._dq = deque(maxlen=self._maxlen)
        self._lock = threading.Lock()

    def put(self, item) -> None:
        """放入新元素；若已满，自动丢弃最旧元素。

        说明：deque(maxlen)天然会在append时丢弃最旧元素；
        为保证线程安全，这里仍然用锁保护append操作。
        """
        with self._lock:
            self._dq.append(item)

    def get_latest(self) -> Tuple[bool, Optional[object]]:
        """一次性取出“当前最新”的元素，并清空旧积压。

        返回：(has_item, item)
        - has_item: 是否成功取到元素
        - item: 取得的最新元素；若无则为None
        """
        with self._lock:
            if not self._dq:
                return False, None

            # 仅保留最后一个（最新），丢弃其余旧项
            latest = self._dq[-1]
            self._dq.clear()
            return True, latest

    def size(self) -> int:
        """获取当前队列大小（仅用于诊断统计）。"""
        with self._lock:
            return len(self._dq)


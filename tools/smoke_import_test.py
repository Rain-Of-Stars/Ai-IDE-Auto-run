# -*- coding: utf-8 -*-
"""
无界面冒烟测试：
- 仅导入核心模块（不会启动GUI）
- 读取并打印全局日志开关状态
- 测试一次状态切换（persist=False）并监听信号回调
注意：不会改写配置文件，也不会启动 QApplication。
"""
from __future__ import annotations

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from auto_approve.app_state import get_app_state
from auto_approve.logger_manager import get_logger


def main() -> int:
    print("OK: starting smoke import")
    state = get_app_state()
    logger = get_logger()

    print("enable_logging (before):", state.enable_logging)

    # 连接信号，验证同步广播（无需事件循环即可同步触发）
    def _on_changed(enabled: bool):
        print("signal: loggingChanged ->", enabled)

    try:
        state.loggingChanged.connect(_on_changed)
    except Exception:
        # 连接失败不影响后续，只打印提示
        print("WARN: connect loggingChanged failed")

    # 切到反值（不持久化，防止写盘）
    try:
        state.set_enable_logging(not state.enable_logging, persist=False, emit_signal=True)
        print("enable_logging (flipped):", state.enable_logging)
        logger.info("测试日志：无界面快速验证（flip）")
    except Exception as e:
        print("ERROR: flip failed:", e)

    # 还原
    try:
        state.set_enable_logging(not state.enable_logging, persist=False, emit_signal=True)
        print("enable_logging (restored):", state.enable_logging)
        logger.info("测试日志：无界面快速验证（restore）")
    except Exception as e:
        print("ERROR: restore failed:", e)

    print("OK: smoke import done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

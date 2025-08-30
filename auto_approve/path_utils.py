# -*- coding: utf-8 -*-
"""路径工具：统一解析应用的基准目录。

优先级：
1) 若为打包后的可执行文件（PyInstaller等），返回exe所在目录；
2) 否则返回主入口脚本（__main__.__file__）所在目录；
3) 再不行则回退到当前工作目录。

这样可避免在打包运行时把文件写入临时解包目录（_MEIPASS）。
"""
from __future__ import annotations
import os
import sys


def get_app_base_dir() -> str:
    """获取应用基准目录（exe或主脚本所在目录）。"""
    # 情况1：被PyInstaller等打包为exe运行
    if getattr(sys, "frozen", False) and hasattr(sys, "executable"):
        return os.path.dirname(sys.executable)

    # 情况2：普通脚本运行，取主模块文件路径
    try:
        import __main__  # 延迟导入，避免循环依赖
        main_file = getattr(__main__, "__file__", None)
        if main_file:
            return os.path.dirname(os.path.abspath(main_file))
    except Exception:
        pass

    # 情况3：回退当前工作目录
    return os.path.abspath(os.getcwd())


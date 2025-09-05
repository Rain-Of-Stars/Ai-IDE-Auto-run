# -*- coding: utf-8 -*-
"""
扫描进程回退顺序计算的单元测试

该测试仅验证纯逻辑函数 `_compute_window_open_plan` 的行为，不依赖真实的WGC或Windows API，
用于确保当配置中的 HWND 失效或未提供时，回退到“按标题/按进程名”的顺序是可预期的。
"""

import types

from workers.scanner_process import _compute_window_open_plan


def _make_cfg(**kwargs):
    """构造一个最小可用的配置对象（使用简单的动态对象）。
    这里不引入真实的 AppConfig，避免额外依赖。
    """
    cfg = types.SimpleNamespace()
    # 默认字段
    setattr(cfg, 'target_hwnd', 0)
    setattr(cfg, 'target_window_title', '')
    setattr(cfg, 'window_title', '')
    setattr(cfg, 'target_process', '')
    # 允许覆盖
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


def test_plan_with_hwnd_title_process():
    """当同时提供 HWND/标题/进程名时，顺序应为：HWND -> 标题 -> 进程名。"""
    cfg = _make_cfg(target_hwnd=123456, target_window_title='Code', target_process='Code.exe')
    plan = _compute_window_open_plan(cfg)
    assert plan == [("hwnd", 123456), ("title", "Code"), ("process", "Code.exe")]


def test_plan_without_hwnd_but_title():
    """没有HWND但有标题时，顺序应为：标题 -> 进程名(若有)。"""
    cfg = _make_cfg(target_hwnd=0, target_window_title='VSCode', target_process='Code.exe')
    plan = _compute_window_open_plan(cfg)
    assert plan[0] == ("title", "VSCode")
    assert plan[1] == ("process", "Code.exe")


def test_plan_empty_when_no_identifier():
    """当既无HWND也无标题与进程名时，计划应为空列表。"""
    cfg = _make_cfg()
    plan = _compute_window_open_plan(cfg)
    assert plan == []


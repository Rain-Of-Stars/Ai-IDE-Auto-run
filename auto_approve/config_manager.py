# -*- coding: utf-8 -*-
"""
配置管理模块：负责加载、保存与提供默认配置。
所有配置以 JSON 文件持久化，便于用户定制和下次启动自动生效。
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List

CONFIG_FILE = "config.json"


@dataclass
class ROI:
    # 屏幕区域：若 w 或 h 为 0 则表示使用整个监视器区域
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0


@dataclass
class AppConfig:
    # 模板图片路径（单个，兼容旧版本）
    template_path: str = "assets/images/approve_pix.png"
    # 多模板路径列表：如非空，则以此为准；为空则回退到 template_path
    template_paths: List[str] = field(default_factory=list)
    # 监视器索引，mss 的 monitors 为 1 开始计数
    monitor_index: int = 1
    # 截屏 ROI
    roi: ROI = field(default_factory=ROI)
    # 扫描间隔（毫秒），越大越省电
    interval_ms: int = 800
    # 匹配阈值 [0,1]
    threshold: float = 0.88
    # 匹配到后冷却时间（秒），避免重复点击
    cooldown_s: float = 5.0
    # 是否启用日志
    enable_logging: bool = False
    # 是否启用托盘通知
    enable_notifications: bool = True
    # 是否将图像转灰度后再匹配，降低计算量
    grayscale: bool = True
    # 是否进行多尺度匹配
    multi_scale: bool = False
    # 多尺度列表（仅在 multi_scale 为 True 时生效）
    scales: tuple = field(default_factory=lambda: (1.0, 1.25, 0.8))
    # 点击偏移（像素），用于点击模板中心附近位置
    click_offset: tuple = field(default_factory=lambda: (0, 0))
    # 连续命中帧次数，>= 此次数才触发点击，降低误报
    min_detections: int = 1
    # 是否启动后自动开始扫描
    auto_start_scan: bool = True
    
    # === 调试和多屏幕支持配置 ===
    # 是否启用调试模式（显示详细坐标信息）
    debug_mode: bool = False
    # 是否保存调试截图
    save_debug_images: bool = False
    # 调试图片保存目录
    debug_image_dir: str = "debug_images"
    # 是否启用坐标校正（用于多屏幕环境）
    enable_coordinate_correction: bool = True
    # 坐标校正偏移量（x, y）
    coordinate_offset: tuple = field(default_factory=lambda: (0, 0))
    # 是否使用增强的窗口查找算法
    enhanced_window_finding: bool = True
    # 点击方法：'message'（Windows消息）或 'simulate'（模拟点击）
    click_method: str = "message"
    # 是否在点击前验证窗口位置
    verify_window_before_click: bool = True
    # 多屏幕环境下的坐标转换模式：'auto'、'manual'、'disabled'
    coordinate_transform_mode: str = "auto"
    # 是否启用多屏幕轮询搜索（在所有屏幕上搜索目标）
    enable_multi_screen_polling: bool = False
    # 多屏幕轮询时的屏幕切换间隔（毫秒）
    screen_polling_interval_ms: int = 1000

    # === Windows Graphics Capture (WGC) 相关配置 ===
    # 捕获模式：window(窗口捕获) 或 monitor(显示器捕获)
    capture_backend: str = "window"
    # 是否使用显示器捕获模式（False=窗口模式，True=显示器模式）
    use_monitor: bool = False
    # 目标窗口句柄（0 表示未设置）
    target_hwnd: int = 0
    # 目标窗口标题（用于自动查找HWND，可选）
    target_window_title: str = ""
    # 标题匹配是否允许部分匹配
    window_title_partial_match: bool = True
    # 目标进程（名称或完整路径，支持部分匹配）
    target_process: str = ""
    # 进程匹配是否允许部分匹配
    process_partial_match: bool = True
    # 窗口抓帧最大FPS
    fps_max: int = 30
    # 单次抓帧超时（毫秒）
    capture_timeout_ms: int = 5000
    # 处理最小化：是否恢复但不激活（不抢占前台）
    restore_minimized_noactivate: bool = True
    # 抓帧后是否重新最小化
    restore_minimized_after_capture: bool = False
    # Electron/Chromium优化建议开关（仅用于提示，不强制）
    enable_electron_optimization: bool = True

    # === WGC 专用配置 ===
    # 是否包含鼠标光标
    include_cursor: bool = False
    # 兼容旧配置：统一边框开关（已废弃，保留字段便于读取旧配置）
    border_required: bool = False
    # 新增：分别控制窗口与屏幕边框
    window_border_required: bool = False
    screen_border_required: bool = False
    # 脏区域模式（暂未实现）
    dirty_region_mode: str = ""


def _default_config_dict() -> Dict[str, Any]:
    cfg = AppConfig()
    d = asdict(cfg)
    # dataclasses 的嵌套需要手动展开子对象
    d["roi"] = asdict(cfg.roi)
    # 将 tuple 改为 list 以便 JSON 持久化
    d["scales"] = list(cfg.scales)
    d["click_offset"] = list(cfg.click_offset)
    return d


def ensure_config_exists(path: Optional[str] = None) -> str:
    """确保配置文件存在；不存在则创建默认配置。
    返回配置文件绝对路径。
    """
    config_path = os.path.abspath(path or CONFIG_FILE)
    if not os.path.exists(config_path):
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(_default_config_dict(), f, ensure_ascii=False, indent=2)
    return config_path


def _migrate_capture_backend(backend: str) -> str:
    """迁移旧的捕获后端配置到新的WGC模式"""
    if backend in ['screen', 'auto']:
        return 'monitor'  # 传统屏幕截取和自动模式映射为显示器捕获
    elif backend == 'wgc':
        return 'window'   # 旧的wgc配置映射为窗口捕获
    return backend  # window, monitor 保持不变


def load_config(path: Optional[str] = None) -> AppConfig:
    """从 JSON 读取配置，读取失败时回退默认配置并自动写回。"""
    config_path = ensure_config_exists(path)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        # 发生损坏时重置
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(_default_config_dict(), f, ensure_ascii=False, indent=2)
        data = _default_config_dict()

    # 构造 AppConfig
    roi_data = data.get("roi", {})
    roi = ROI(
        x=int(roi_data.get("x", 0)),
        y=int(roi_data.get("y", 0)),
        w=int(roi_data.get("w", 0)),
        h=int(roi_data.get("h", 0)),
    )

    # 读取并迁移捕获后端；同时根据是否存在 use_monitor 字段决定兼容行为
    # 若配置文件中没有 use_monitor，则按 capture_backend 推断（monitor=>True，否则False）
    _backend = _migrate_capture_backend(str(data.get("capture_backend", "window")))
    if "use_monitor" in data:
        _use_monitor = bool(data.get("use_monitor"))
    else:
        _use_monitor = (_backend == "monitor")

    # 读取新旧边框配置：若新字段不存在则回退到旧的 border_required
    _border_required_legacy = bool(data.get("border_required", False))
    _window_border_required = bool(data.get("window_border_required", _border_required_legacy))
    _screen_border_required = bool(data.get("screen_border_required", _border_required_legacy))

    cfg = AppConfig(
        template_path=str(data.get("template_path", "approve_pix.png")),
        # 新增：多模板路径，若为空则由使用方回退到 template_path
        template_paths=list(data.get("template_paths", [])),
        monitor_index=int(data.get("monitor_index", 1)),
        roi=roi,
        interval_ms=int(data.get("interval_ms", 800)),
        threshold=float(data.get("threshold", 0.88)),
        cooldown_s=float(data.get("cooldown_s", 5.0)),
        enable_logging=bool(data.get("enable_logging", False)),
        enable_notifications=bool(data.get("enable_notifications", True)),
        grayscale=bool(data.get("grayscale", True)),
        multi_scale=bool(data.get("multi_scale", False)),
        scales=tuple(data.get("scales", [1.0, 1.25, 0.8])),
        click_offset=tuple(data.get("click_offset", [0, 0])),
        min_detections=int(data.get("min_detections", 1)),
        auto_start_scan=bool(data.get("auto_start_scan", True)),
        # 新增的调试和多屏幕支持配置
        debug_mode=bool(data.get("debug_mode", False)),
        save_debug_images=bool(data.get("save_debug_images", False)),
        debug_image_dir=str(data.get("debug_image_dir", "debug_images")),
        enable_coordinate_correction=bool(data.get("enable_coordinate_correction", True)),
        coordinate_offset=tuple(data.get("coordinate_offset", [0, 0])),
        enhanced_window_finding=bool(data.get("enhanced_window_finding", True)),
        click_method=str(data.get("click_method", "message")),
        verify_window_before_click=bool(data.get("verify_window_before_click", True)),
        coordinate_transform_mode=str(data.get("coordinate_transform_mode", "auto")),
        enable_multi_screen_polling=bool(data.get("enable_multi_screen_polling", False)),
        screen_polling_interval_ms=int(data.get("screen_polling_interval_ms", 1000)),
        # WGC 捕获相关（兼容旧配置）
        capture_backend=_backend,
        use_monitor=_use_monitor,
        target_hwnd=int(data.get("target_hwnd", 0)),
        target_window_title=str(data.get("target_window_title", "")),
        window_title_partial_match=bool(data.get("window_title_partial_match", True)),
        # 新增：进程匹配相关
        target_process=str(data.get("target_process", "")),
        process_partial_match=bool(data.get("process_partial_match", True)),
        fps_max=int(data.get("fps_max", 30)),
        capture_timeout_ms=int(data.get("capture_timeout_ms", 5000)),
        restore_minimized_noactivate=bool(data.get("restore_minimized_noactivate", True)),
        restore_minimized_after_capture=bool(data.get("restore_minimized_after_capture", False)),
        enable_electron_optimization=bool(data.get("enable_electron_optimization", True)),
        # WGC 专用配置
        include_cursor=bool(data.get("include_cursor", False)),
        # 旧字段仍写回，以便兼容读取；内部代码不再使用该字段
        border_required=_border_required_legacy,
        window_border_required=_window_border_required,
        screen_border_required=_screen_border_required,
    )
    return cfg


def save_config(cfg: AppConfig, path: Optional[str] = None) -> str:
    """保存配置到 JSON，返回保存路径。"""
    data = asdict(cfg)
    data["roi"] = asdict(cfg.roi)
    data["scales"] = list(cfg.scales)
    data["click_offset"] = list(cfg.click_offset)
    # 兼容处理：若存在多模板列表，则保留 template_path 为列表首元素，便于旧字段读取
    if isinstance(data.get("template_paths"), list):
        if data["template_paths"]:
            data["template_path"] = data["template_paths"][0]
        else:
            # 若列表为空，确保至少有一个回退路径
            data["template_paths"] = []
    data["coordinate_offset"] = list(cfg.coordinate_offset)
    config_path = os.path.abspath(path or CONFIG_FILE)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return config_path

# -*- coding: utf-8 -*-
"""屏幕扫描线程：使用 Windows Graphics Capture (WGC) + OpenCV 模板匹配，命中后触发无感点击。
- 高性能：基于 WGC 的硬件加速捕获，支持后台/遮挡/最大化窗口稳定采集
- 低占用：按 interval_ms 定时扫描，尽量少的内存拷贝；可选灰度匹配
- 支持 ROI + 多显示器；支持多尺度匹配以应对缩放
- 通过 cooldown_s 限制点击频率，min_detections 降低误报
- DPI 感知：正确处理不同缩放比例下的坐标转换
"""
from __future__ import annotations
import os
import time
import threading
from typing import List, Tuple, Optional

import numpy as np
import cv2
from PySide6 import QtCore

from auto_approve.config_manager import AppConfig, ROI
from auto_approve.path_utils import get_app_base_dir
from auto_approve.logger_manager import get_logger
from auto_approve.win_clicker import post_click_with_config, post_click_in_window_with_config
from auto_approve.performance_optimizer import PerformanceOptimizer
from tools.performance_monitor import get_performance_monitor

# WGC 后端
from capture import CaptureManager, enum_windows, get_monitor_handles, get_all_monitors_info
from capture.monitor_utils import find_window_by_title, find_window_by_process, is_electron_process
from utils.win_dpi import set_process_dpi_awareness, get_dpi_info_summary

import ctypes
from ctypes import wintypes


class ScannerWorker(QtCore.QThread):
    """基于 WGC 的模板扫描与无感点击线程。"""

    # 状态文本（用于托盘提示）
    sig_status = QtCore.Signal(str)
    # 命中信号：score, sx, sy（屏幕坐标）
    sig_hit = QtCore.Signal(float, int, int)
    # 错误或日志文本
    sig_log = QtCore.Signal(str)
    # 跨线程配置更新信号（从UI线程发射，在线程内执行update_config）
    sig_update_config = QtCore.Signal(object)

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        # 将跨线程配置更新信号连接到挂起配置接口，由工作线程循环应用，避免阻塞UI线程
        try:
            self.sig_update_config.connect(self.request_update_config)
        except Exception:
            pass
        self._running = False
        self._next_allowed = 0.0
        self._consecutive = 0
        self._logger = get_logger()

        # 模板缓存：(tpl图像, (w,h))，包含所有模板、所有尺度
        self._templates: List[Tuple[np.ndarray, Tuple[int, int]]] = []
        # 已加载模板签名（用于避免重复加载），由多模板路径与关键配置组合而成
        self._tpl_loaded_key: str = ""

        # WGC 捕获管理器
        self._capture_manager: Optional[CaptureManager] = None
        self._current_capture_backend: str = getattr(self.cfg, 'capture_backend', 'wgc')

        # 性能优化器 - 减少工作线程数量以降低CPU占用
        self._performance_optimizer = PerformanceOptimizer(max_workers=1)
        self._last_performance_update = 0.0

        # 性能监控器
        self._performance_monitor = get_performance_monitor()

        # 性能优化：状态更新节流
        self._last_status_update = 0.0
        self._status_update_interval = 0.5  # 每500ms最多更新一次状态
        self._last_status_text = ""

        # 调试和多屏幕支持相关
        self._debug_counter = 0
        self._monitor_info_cache = None
        self._last_monitor_check = 0.0
        # 多屏幕轮询相关
        self._current_polling_monitor = 1
        self._last_polling_switch = 0.0
        self._all_monitors_cache = None

        # 性能优化：状态更新节流 - 减少UI刷新频率
        self._last_status_update = 0.0
        self._status_update_interval = 2.0  # 每2秒最多更新一次状态，减少UI卡顿
        self._last_status_text = ""

        # 解析调试目录（相对路径基于应用目录：exe或主脚本目录）并确保存在
        base_dir = get_app_base_dir()
        if os.path.isabs(self.cfg.debug_image_dir):
            self._debug_dir = self.cfg.debug_image_dir
        else:
            self._debug_dir = os.path.join(base_dir, self.cfg.debug_image_dir)
        if self.cfg.save_debug_images:
            os.makedirs(self._debug_dir, exist_ok=True)

        # 窗口捕获相关（已废弃，统一使用WGC）
        self._current_capture_backend: str = getattr(self.cfg, 'capture_backend', 'wgc')
        self._window_find_retries = 0
        self._max_window_find_retries = 3

        # 线程内应用配置的挂起槽与状态
        # 用于挂起配置的线程安全锁
        self._cfg_lock = threading.Lock()

        self._pending_cfg: Optional[AppConfig] = None

    # ---------- 公共控制接口 ----------
    def request_update_config(self, cfg: AppConfig):
        """请求更新配置：线程安全地挂起配置，在工作线程周期性应用。
        注意：避免在UI线程直接执行重型update_config逻辑。"""
        try:
            with self._cfg_lock:
                self._pending_cfg = cfg
        except Exception as e:
            self._logger.warning(f"请求更新配置失败: {e}")


    def _emit_status_throttled(self, status_text: str):
        """节流的状态更新：避免过于频繁的UI更新"""
        now = time.monotonic()

        # 如果状态文本相同且更新间隔未到，则跳过
        if (status_text == self._last_status_text and
            now - self._last_status_update < self._status_update_interval):
            return

        self._last_status_text = status_text
        self._last_status_update = now
        self.sig_status.emit(status_text)

    def update_config(self, cfg: AppConfig):
        """更新运行配置；模板路径变化会重新加载模板，窗口参数变化会重新初始化窗口捕获。"""
        # 检查窗口相关参数是否发生变化
        old_hwnd = getattr(self.cfg, 'target_hwnd', 0)
        old_title = getattr(self.cfg, 'target_window_title', '')
        old_backend = getattr(self.cfg, 'capture_backend', 'screen')

        new_hwnd = getattr(cfg, 'target_hwnd', 0)
        new_title = getattr(cfg, 'target_window_title', '')
        new_backend = getattr(cfg, 'capture_backend', 'screen')

        # 更新配置
        self.cfg = cfg

        # 重新加载模板
        self._load_templates(force=True)

        # 如果窗口相关参数发生变化，重新初始化WGC捕获管理器
        if (old_hwnd != new_hwnd or old_title != new_title or old_backend != new_backend):
            self._logger.info(f"窗口参数发生变化，重新初始化WGC捕获: hwnd={old_hwnd}->{new_hwnd}, title='{old_title}'->'{new_title}', backend='{old_backend}'->'{new_backend}'")
            # 清理旧的WGC捕获管理器
            if self._capture_manager:
                try:
                    self._capture_manager.close()
                except Exception as e:
                    self._logger.warning(f"清理旧WGC捕获管理器失败: {e}")
                self._capture_manager = None

            # 重置窗口查找重试次数
            self._window_find_retries = 0

    def _apply_pending_config_if_any(self):
        """在工作线程中应用挂起的配置，避免UI线程阻塞。"""
        try:
            with self._cfg_lock:
                pending = self._pending_cfg
                self._pending_cfg = None
            if pending is not None:
                # 在工作线程内应用配置
                self.update_config(pending)
        except Exception as e:
            self._logger.warning(f"应用挂起配置失败: {e}")
            self._window_find_retries = 0

    def stop(self):
        self._running = False
        # 清理性能优化器资源
        if hasattr(self, '_performance_optimizer'):
            self._performance_optimizer.cleanup()

    # ---------- 核心线程逻辑 ----------

    def run(self):
        """主运行循环：统一使用 WGC 后端"""
        self._running = True
        self._consecutive = 0
        self._next_allowed = 0.0
        self._load_templates(force=True)

        # 设置 DPI 感知
        set_process_dpi_awareness()

        # 记录 DPI 信息
        if self.cfg.debug_mode:
            dpi_info = get_dpi_info_summary()
            self._logger.info(f"DPI 信息: {dpi_info}")

        # 统一使用 WGC 后端
        backend = (getattr(self.cfg, 'capture_backend', 'wgc') or 'wgc').lower()
        use_monitor = getattr(self.cfg, 'use_monitor', False)

        if use_monitor:
            self._run_monitor_capture_loop()
        else:
            self._run_window_capture_loop()

    # ---------- 私有工具函数 ----------

    def _get_monitor_info(self, force_refresh: bool = False) -> dict:
        """获取显示器信息，带缓存机制（基于 WGC）。"""
        now = time.monotonic()
        if force_refresh or self._monitor_info_cache is None or (now - self._last_monitor_check) > 5.0:
            monitors = get_all_monitors_info()
            idx = getattr(self.cfg, 'monitor_index', 0)

            # 确保索引有效
            if idx < 0 or idx >= len(monitors):
                idx = 0  # 默认使用第一个显示器（通常是主显示器）

            if monitors:
                mon = monitors[idx]
                self._monitor_info_cache = {
                    'monitor': mon,
                    'index': idx,
                    'total_monitors': len(monitors),
                    'hmonitor': mon['hmonitor']
                }
            else:
                # 没有显示器信息时的默认值
                self._monitor_info_cache = {
                    'monitor': {'left': 0, 'top': 0, 'width': 1920, 'height': 1080},
                    'index': 0,
                    'total_monitors': 1,
                    'hmonitor': None
                }

            self._last_monitor_check = now

            if self.cfg.debug_mode:
                self._logger.info(f"显示器信息更新: 使用显示器{idx}, 总数{self._monitor_info_cache['total_monitors']}")
                self._logger.info(f"显示器{idx}区域: {self._monitor_info_cache['monitor']}")

        return self._monitor_info_cache

    def _get_all_monitors_info(self, force_refresh: bool = False) -> List[dict]:
        """获取所有显示器信息，用于多屏幕轮询（基于 WGC）。"""
        now = time.monotonic()
        if force_refresh or self._all_monitors_cache is None or (now - self._last_monitor_check) > 5.0:
            self._all_monitors_cache = get_all_monitors_info()
            self._last_monitor_check = now

            if self.cfg.debug_mode:
                self._logger.info(f"所有显示器信息更新: 共{len(self._all_monitors_cache)}个显示器")
                for i, info in enumerate(self._all_monitors_cache):
                    self._logger.info(f"显示器{i}: {info}")

        return self._all_monitors_cache



    def _apply_coordinate_correction(self, x: int, y: int) -> Tuple[int, int]:
        """应用坐标校正。"""
        if not self.cfg.enable_coordinate_correction:
            return x, y

        offset_x, offset_y = self.cfg.coordinate_offset
        corrected_x = x + offset_x
        corrected_y = y + offset_y

        if self.cfg.debug_mode:
            self._logger.info(f"坐标校正: ({x},{y}) -> ({corrected_x},{corrected_y}), 偏移({offset_x},{offset_y})")

        return corrected_x, corrected_y

    def _save_debug_image(self, img: np.ndarray, prefix: str, extra_info: str = "") -> None:
        """保存调试图片到内存 - 避免磁盘IO"""
        if not self.cfg.save_debug_images:
            return

        try:
            # 使用内存调试管理器
            from utils.memory_debug_manager import get_debug_manager

            debug_manager = get_debug_manager()

            # 确保调试管理器已启用
            if not debug_manager._enabled:
                debug_manager.enable(True)

            # 生成调试名称
            self._debug_counter += 1
            debug_name = f"{prefix}_{self._debug_counter:04d}"
            if extra_info:
                debug_name = f"{prefix}_{extra_info}_{self._debug_counter:04d}"

            # 保存到内存
            image_id = debug_manager.save_debug_image(
                image=img,
                name=debug_name,
                category="scanner",
                metadata={
                    'timestamp': time.time(),
                    'shape': img.shape,
                    'prefix': prefix,
                    'extra_info': extra_info,
                    'counter': self._debug_counter
                }
            )

            if image_id and self.cfg.debug_mode:
                self._logger.info(f"调试图片已保存到内存: {debug_name} (ID: {image_id})")

        except Exception as e:
            self._logger.error(f"保存调试图片到内存失败: {e}")

            # 回退到磁盘保存（仅在内存方式失败时）
            try:
                self._debug_counter += 1
                timestamp = int(time.time() * 1000)
                filename = f"{prefix}_{timestamp}_{self._debug_counter:04d}.png"
                if extra_info:
                    filename = f"{prefix}_{extra_info}_{timestamp}_{self._debug_counter:04d}.png"

                filepath = os.path.join(self._debug_dir, filename)
                cv2.imwrite(filepath, img)
                if self.cfg.debug_mode:
                    self._logger.info(f"调试图片已保存到磁盘（回退）: {filepath}")
            except Exception as fallback_e:
                self._logger.error(f"磁盘保存调试图片也失败: {fallback_e}")

    def _validate_coordinates(self, x: int, y: int, monitor_info: dict) -> bool:
        """验证坐标是否在有效范围内。"""
        virtual_screen = monitor_info['virtual_screen']

        # 检查是否在虚拟屏幕范围内
        if (x < virtual_screen['left'] or
            x >= virtual_screen['left'] + virtual_screen['width'] or
            y < virtual_screen['top'] or
            y >= virtual_screen['top'] + virtual_screen['height']):

            if self.cfg.debug_mode:
                self._logger.warning(f"坐标({x},{y})超出虚拟屏幕范围{virtual_screen}")
            return False

        return True

    def _load_templates(self, force: bool = False):
        """加载并缓存模板图像（支持多模板、可选多尺度）- 使用内存模板管理器"""
        # 组装当前模板签名：多路径 + 灰度/多尺度/倍率
        paths: List[str] = []
        proj_root = get_app_base_dir()
        if getattr(self.cfg, "template_paths", None):
            for p in self.cfg.template_paths:
                p = str(p).strip()
                if not p:
                    continue
                if os.path.isabs(p):
                    paths.append(p)
                else:
                    # 相对路径基于项目根目录
                    paths.append(os.path.join(proj_root, p))
        if not paths:
            # 回退单路径
            p = str(self.cfg.template_path).strip()
            if os.path.isabs(p):
                paths = [p]
            else:
                paths = [os.path.join(proj_root, p)]

        key = "|".join([
            ";".join(paths),
            f"gray={int(bool(self.cfg.grayscale))}",
            f"ms={int(bool(self.cfg.multi_scale))}",
            f"scales={','.join([f'{s:g}' for s in (self.cfg.scales if self.cfg.multi_scale else (1.0,))])}"
        ])

        if not force and self._templates and self._tpl_loaded_key == key:
            return

        # 尝试使用内存模板管理器
        try:
            from utils.memory_template_manager import get_template_manager

            template_manager = get_template_manager()

            # 预加载所有模板到内存
            loaded_count = template_manager.load_templates(paths, force_reload=force)

            if loaded_count > 0:
                # 从内存获取模板数据并应用配置
                self._templates.clear()
                self._tpl_loaded_key = key

                memory_templates = template_manager.get_templates(paths)
                total_tpl_count = 0

                for template_data, (tw, th) in memory_templates:
                    # 应用灰度转换
                    if self.cfg.grayscale:
                        if template_data.ndim == 3:
                            template_data = cv2.cvtColor(template_data, cv2.COLOR_BGR2GRAY)
                    else:
                        if template_data.ndim == 2:
                            template_data = cv2.cvtColor(template_data, cv2.COLOR_GRAY2BGR)

                    # 应用多尺度
                    scales = self.cfg.scales if self.cfg.multi_scale else (1.0,)
                    for s in scales:
                        if s <= 0:
                            continue
                        if s == 1.0:
                            tpl = template_data.copy()
                        else:
                            h, w = template_data.shape[:2]
                            tpl = cv2.resize(template_data, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
                        th, tw = tpl.shape[:2]
                        if th < 2 or tw < 2:
                            continue
                        self._templates.append((tpl, (tw, th)))
                        total_tpl_count += 1

                self.sig_log.emit(f"从内存加载模板完成，路径数={len(paths)}，总尺度数={total_tpl_count}")
                return

        except Exception as e:
            self._logger.warning(f"内存模板管理器加载失败，回退到传统方式: {e}")

        # 回退到传统的磁盘加载方式
        self._templates.clear()
        self._tpl_loaded_key = key

        total_tpl_count = 0
        missing_files: List[str] = []

        # 资源回退目录（assets/images）
        assets_img_dir = os.path.join(proj_root, 'assets', 'images')

        for path in paths:
            load_path = path
            if not os.path.exists(load_path):
                # 兼容旧配置：仅给出文件名或旧根目录相对路径时，尝试在 assets/images 下查找
                candidate = os.path.join(assets_img_dir, os.path.basename(path))
                if os.path.exists(candidate):
                    load_path = candidate
                else:
                    missing_files.append(path)
                    continue

            img = cv2.imdecode(np.fromfile(load_path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            if img is None:
                # imread 对中文路径可能失败，已用 imdecode；若仍失败则跳过
                self.sig_log.emit(f"无法读取模板图像: {load_path}")
                continue

            # 转灰度可降低计算量
            if self.cfg.grayscale:
                if img.ndim == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                if img.ndim == 2:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

            scales = self.cfg.scales if self.cfg.multi_scale else (1.0,)
            per_path_count = 0
            for s in scales:
                if s <= 0:
                    continue
                if s == 1.0:
                    tpl = img.copy()
                else:
                    h, w = img.shape[:2]
                    tpl = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
                th, tw = tpl.shape[:2]
                if th < 2 or tw < 2:
                    continue
                self._templates.append((tpl, (tw, th)))
                per_path_count += 1
            total_tpl_count += per_path_count

        # 日志反馈
        if missing_files:
            self.sig_log.emit("以下模板文件不存在: " + "; ".join(missing_files))
        self.sig_log.emit(f"模板已加载，路径数={len(paths)}，总尺度数={total_tpl_count}")



    def _match_best(self, img: np.ndarray) -> Tuple[float, Tuple[int, int], Tuple[int, int]]:
        """在 img 中进行模板匹配，返回 (best_score, best_loc(x,y), best_tpl_size(w,h))。
        使用性能优化器进行高效匹配。
        """
        # 获取模板路径列表
        template_paths = self._get_template_paths()
        if not template_paths:
            return 0.0, (0, 0), (0, 0)

        # 使用性能优化器进行匹配
        best_score, best_loc, best_wh = self._performance_optimizer.optimize_template_matching(
            img, template_paths, self.cfg.threshold, self.cfg.grayscale
        )

        # 定期更新性能统计 - 降低更新频率
        now = time.monotonic()
        if now - self._last_performance_update > 30.0:  # 每30秒更新一次，减少开销
            self._performance_optimizer.update_performance_stats()
            self._last_performance_update = now

        return best_score, best_loc, best_wh

    def _get_template_paths(self) -> List[str]:
        """获取模板路径列表"""
        base_dir = get_app_base_dir()
        template_paths = []

        # 优先使用多模板路径
        if self.cfg.template_paths:
            for path in self.cfg.template_paths:
                if not os.path.isabs(path):
                    path = os.path.join(base_dir, path)
                if os.path.exists(path):
                    template_paths.append(path)
        else:
            # 回退到单模板路径
            path = self.cfg.template_path
            if not os.path.isabs(path):
                path = os.path.join(base_dir, path)
            if os.path.exists(path):
                template_paths.append(path)

        return template_paths



    # ---------- 统一使用WGC ----------



    def _run_window_capture_loop(self) -> None:
        """WGC 窗口捕获主循环"""
        self._logger.info("启动 WGC 窗口捕获循环")

        # 初始化捕获管理器
        if not self._init_capture_manager():
            self.sig_status.emit("WGC 窗口捕获初始化失败")
            return

        try:
            while self._running:
                t0 = time.monotonic()
                try:
                    # 在线程循环里应用可能挂起的配置
                    self._apply_pending_config_if_any()

                    score = self._scan_wgc_and_maybe_click()
                    backend_desc = "WGC 窗口捕获"
                    status_msg = f"运行中 | 后端: {backend_desc} | 上次匹配: {score:.3f}"
                    self._emit_status_throttled(status_msg)
                except Exception as e:
                    self._logger.exception("WGC 窗口扫描异常: %s", e)
                    self.sig_log.emit(f"WGC 窗口扫描异常: {e}")

                dt = (time.monotonic() - t0) * 1000.0
                # 使用自适应间隔控制
                adaptive_interval = self._performance_optimizer.get_adaptive_interval(self.cfg.interval_ms)
                sleep_ms = max(0, int(adaptive_interval - dt))
                if sleep_ms > 0:
                    time.sleep(sleep_ms / 1000.0)
        finally:
            self._cleanup_capture_manager()

    def _run_monitor_capture_loop(self) -> None:
        """WGC 显示器捕获主循环"""
        self._logger.info("启动 WGC 显示器捕获循环")

        # 初始化显示器捕获
        if not self._init_monitor_capture():
            self.sig_status.emit("WGC 显示器捕获初始化失败")
            return

        try:
            while self._running:
                t0 = time.monotonic()
                try:
                    # 在线程循环里应用可能挂起的配置
                    self._apply_pending_config_if_any()

                    score = self._scan_wgc_and_maybe_click()
                    backend_desc = "WGC 显示器捕获"

                    if getattr(self.cfg, 'enable_multi_screen_polling', False):
                        current_monitor = getattr(self, '_current_polling_monitor', 0)
                        status_msg = f"运行中 | 后端: {backend_desc} | 多屏轮询 | 当前屏幕: {current_monitor} | 匹配: {score:.3f}"
                    else:
                        status_msg = f"运行中 | 后端: {backend_desc} | 上次匹配: {score:.3f}"
                    self._emit_status_throttled(status_msg)
                except Exception as e:
                    self._logger.exception("WGC 显示器扫描异常: %s", e)
                    self.sig_log.emit(f"WGC 显示器扫描异常: {e}")

                dt = (time.monotonic() - t0) * 1000.0
                # 使用自适应间隔控制
                adaptive_interval = self._performance_optimizer.get_adaptive_interval(self.cfg.interval_ms)
                sleep_ms = max(0, int(adaptive_interval - dt))
                if sleep_ms > 0:
                    time.sleep(sleep_ms / 1000.0)
        finally:
            self._cleanup_capture_manager()

    def _apply_roi_to_image(self, img: np.ndarray) -> Tuple[np.ndarray, int, int]:
        """将配置的ROI应用到窗口图像上，返回(裁剪图, roi_left, roi_top)。"""
        roi: ROI = self.cfg.roi
        h, w = img.shape[:2]
        if roi.w > 0 and roi.h > 0:
            x = max(0, min(int(roi.x), w - 1))
            y = max(0, min(int(roi.y), h - 1))
            rw = max(1, min(int(roi.w), w - x))
            rh = max(1, min(int(roi.h), h - y))
            return img[y:y+rh, x:x+rw].copy(), x, y
        return img, 0, 0

    def _get_window_rect(self, hwnd: int) -> Tuple[int, int, int, int]:
        """读取窗口矩形（屏幕坐标）。"""
        rect = wintypes.RECT()
        if ctypes.WinDLL('user32', use_last_error=True).GetWindowRect(hwnd, ctypes.byref(rect)):
            return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
        return 0, 0, 0, 0



    # ---------- 新的 WGC 相关函数 ----------

    def _init_capture_manager(self) -> bool:
        """初始化 WGC 捕获管理器（窗口模式）"""
        try:
            self._capture_manager = CaptureManager()

            # 配置捕获参数
            fps = getattr(self.cfg, 'fps_max', 30)
            include_cursor = getattr(self.cfg, 'include_cursor', False)
            # 窗口捕获：使用窗口边框开关
            border_required = bool(getattr(self.cfg, 'window_border_required', getattr(self.cfg, 'border_required', False)))
            restore_minimized = getattr(self.cfg, 'restore_minimized_noactivate', True)

            self._capture_manager.configure(
                fps=fps,
                include_cursor=include_cursor,
                border_required=border_required,
                restore_minimized=restore_minimized
            )

            # 确定目标窗口
            target_hwnd = getattr(self.cfg, 'target_hwnd', 0)
            target_title = getattr(self.cfg, 'target_window_title', '')
            target_process = getattr(self.cfg, 'target_process', '')

            if target_hwnd > 0:
                success = self._capture_manager.open_window(target_hwnd)
            elif target_title:
                partial_match = getattr(self.cfg, 'window_title_partial_match', True)
                success = self._capture_manager.open_window(target_title, partial_match)
            elif target_process:
                partial_match = getattr(self.cfg, 'process_partial_match', True)
                success = self._capture_manager.open_window(target_process, partial_match)
            else:
                self._logger.error("未配置目标窗口")
                return False

            if success:
                self._logger.info("WGC 窗口捕获管理器初始化成功")
                return True
            else:
                self._logger.error("WGC 窗口捕获管理器初始化失败")
                return False

        except Exception as e:
            self._logger.error(f"初始化 WGC 捕获管理器失败: {e}")
            return False

    def _init_monitor_capture(self) -> bool:
        """初始化 WGC 捕获管理器（显示器模式）"""
        try:
            self._capture_manager = CaptureManager()

            # 配置捕获参数
            fps = getattr(self.cfg, 'fps_max', 30)
            include_cursor = getattr(self.cfg, 'include_cursor', False)
            # 显示器捕获：使用屏幕边框开关
            border_required = bool(getattr(self.cfg, 'screen_border_required', getattr(self.cfg, 'border_required', False)))

            self._capture_manager.configure(
                fps=fps,
                include_cursor=include_cursor,
                border_required=border_required,
                restore_minimized=False  # 显示器模式不需要恢复窗口
            )

            # 确定目标显示器，并验证索引有效性
            monitor_index = getattr(self.cfg, 'monitor_index', 0)

            # 验证显示器索引有效性
            from capture.monitor_utils import get_all_monitors_info
            monitors = get_all_monitors_info()
            if monitor_index < 0 or monitor_index >= len(monitors):
                self._logger.warning(f"配置的显示器索引 {monitor_index} 无效，当前系统有 {len(monitors)} 个显示器")
                self._logger.warning(f"自动回退到显示器索引 0 (主显示器)")
                monitor_index = 0  # 回退到主显示器

            success = self._capture_manager.open_monitor(monitor_index)

            if success:
                self._logger.info(f"WGC 显示器捕获管理器初始化成功: monitor_index={monitor_index}")
                return True
            else:
                self._logger.error(f"WGC 显示器捕获管理器初始化失败: monitor_index={monitor_index}")
                return False

        except Exception as e:
            self._logger.error(f"初始化 WGC 显示器捕获失败: {e}")
            return False

    def _cleanup_capture_manager(self):
        """清理捕获管理器"""
        if self._capture_manager:
            try:
                self._capture_manager.close()
                self._logger.info("WGC 捕获管理器已清理")
            except Exception as e:
                self._logger.error(f"清理 WGC 捕获管理器失败: {e}")
            finally:
                self._capture_manager = None

    def _scan_wgc_and_maybe_click(self) -> float:
        """WGC 捕获一次并可能点击 - 带性能监控"""
        # 开始性能监控
        scan_id = self._performance_monitor.start_scan()

        # 模板就绪检查
        if not self._templates:
            self._load_templates(force=True)
            if not self._templates:
                self.sig_status.emit("模板未就绪")
                time.sleep(0.5)
                return 0.0

        if not self._capture_manager:
            self._logger.error("WGC 捕获管理器未初始化")
            return 0.0

        # 捕获帧 - 监控捕获性能
        capture_start = time.monotonic()
        restore_after = getattr(self.cfg, 'restore_minimized_after_capture', False)
        img = self._capture_manager.capture_frame(restore_after_capture=restore_after)
        capture_time = (time.monotonic() - capture_start) * 1000

        # 记录捕获性能
        frame_size = img.nbytes if img is not None else 0
        self._performance_monitor.record_capture_time(capture_time, frame_size)

        if img is None:
            if self.cfg.debug_mode:
                self._logger.warning("WGC 捕获帧失败")
            return 0.0

        if self.cfg.save_debug_images:
            self._save_debug_image(img, "wgc_capture")

        # 应用 ROI
        roi_img, roi_left, roi_top = self._apply_roi_to_image(img)

        if self.cfg.save_debug_images:
            self._save_debug_image(roi_img, "wgc_roi")

        # 模板匹配 - 监控匹配性能
        match_start = time.monotonic()
        best_score = 0.0
        best_loc = None
        best_template_size = None

        for i, (tpl, (tw, th)) in enumerate(self._templates):
            if self.cfg.grayscale:
                gray_roi = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY) if len(roi_img.shape) == 3 else roi_img
                gray_tpl = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY) if len(tpl.shape) == 3 else tpl
                result = cv2.matchTemplate(gray_roi, gray_tpl, cv2.TM_CCOEFF_NORMED)
            else:
                result = cv2.matchTemplate(roi_img, tpl, cv2.TM_CCOEFF_NORMED)

            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > best_score:
                best_score = max_val
                best_loc = max_loc
                best_template_size = (tw, th)

            # 早期退出优化
            if max_val > 0.85:
                self._logger.debug(f"早期退出: 模板{i+1}/{len(self._templates)}, 分数={max_val:.3f}")
                break

        match_time = (time.monotonic() - match_start) * 1000
        self._performance_monitor.record_match_time(match_time, len(self._templates))

        # 检查是否达到阈值
        if best_score >= self.cfg.threshold and best_loc is not None:
            # 计算点击坐标（相对于原图）
            tw, th = best_template_size
            click_x = roi_left + best_loc[0] + tw // 2 + self.cfg.click_offset[0]
            click_y = roi_top + best_loc[1] + th // 2 + self.cfg.click_offset[1]

            # 执行点击
            self._perform_wgc_click(click_x, click_y, best_score)

        # 完成性能监控
        self._performance_monitor.finish_scan(scan_id)

        return best_score

    def _perform_wgc_click(self, x: int, y: int, score: float):
        """执行 WGC 模式下的点击"""
        now = time.monotonic()
        if now < self._next_allowed:
            return

        # 获取捕获统计信息
        stats = self._capture_manager.get_stats() if self._capture_manager else {}
        target_hwnd = stats.get('target_hwnd')

        if target_hwnd:
            # 窗口模式：使用窗口内点击
            ok = post_click_in_window_with_config(target_hwnd, int(x), int(y), self.cfg)
            if ok:
                self._logger.info("WGC 窗口点击成功: score=%.3f, pos=(%d,%d), hwnd=%d", score, x, y, target_hwnd)
                self.sig_hit.emit(score, int(x), int(y))
                self._next_allowed = now + max(0.0, float(self.cfg.cooldown_s))
            else:
                self._logger.warning("WGC 窗口点击失败: pos=(%d,%d), hwnd=%d", x, y, target_hwnd)
                self.sig_log.emit(f"WGC 窗口点击失败: ({x},{y})")
        else:
            # 显示器模式：使用屏幕坐标点击
            ok = post_click_with_config(int(x), int(y), self.cfg)
            if ok:
                self._logger.info("WGC 显示器点击成功: score=%.3f, pos=(%d,%d)", score, x, y)
                self.sig_hit.emit(score, int(x), int(y))
                self._next_allowed = now + max(0.0, float(self.cfg.cooldown_s))
            else:
                self._logger.warning("WGC 显示器点击失败: pos=(%d,%d)", x, y)
                self.sig_log.emit(f"WGC 显示器点击失败: ({x},{y})")

        self._consecutive = 0

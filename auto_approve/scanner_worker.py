# -*- coding: utf-8 -*-
"""屏幕扫描线程：使用 mss 截屏 + OpenCV 模板匹配，命中后触发无感点击。
- 低占用：按 interval_ms 定时扫描，尽量少的内存拷贝；可选灰度匹配。
- 支持 ROI + 多显示器；支持多尺度匹配以应对缩放。
- 通过 cooldown_s 限制点击频率，min_detections 降低误报。
- 增强多屏幕支持：坐标校正、调试模式、边界检查。
"""
from __future__ import annotations
import os
import time
from typing import List, Tuple

import numpy as np
import cv2
import mss
from PySide6 import QtCore

from auto_approve.config_manager import AppConfig, ROI
from auto_approve.path_utils import get_app_base_dir
from auto_approve.logger_manager import get_logger
from auto_approve.win_clicker import post_click_with_config, get_foreground_window_info, start_foreground_watcher, stop_foreground_watcher
from auto_approve.scheduler import AdaptiveScanScheduler, SchedulerConfig

import ctypes
from ctypes import wintypes
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
user32 = ctypes.WinDLL('user32', use_last_error=True)


class TemplateBank:
    """模板仓库：统一预处理为灰度边缘域，并构建固定尺度金字塔。
    - 读入：cv2.IMREAD_GRAYSCALE
    - 边缘：Canny（更鲁棒），可回退Sobel
    - 尺度：固定 [0.9, 1.0, 1.1]
    - 轮询：get_next_batch(k) 每轮仅返回最多k个模板，控制单次计算负载
    """

    def __init__(self):
        self.templates: List[Tuple[np.ndarray, Tuple[int, int]]] = []
        self.cursor: int = 0

    def clear(self):
        self.templates.clear()
        self.cursor = 0

    def load_from_paths(self, paths: List[str]) -> int:
        self.clear()
        total = 0
        scales = [0.9, 1.0, 1.1]
        for p in paths:
            try:
                data = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            except Exception:
                data = None
            if data is None:
                continue
            # 边缘域
            try:
                edge = cv2.Canny(data, 60, 180)
            except Exception:
                # 回退Sobel
                gx = cv2.Sobel(data, cv2.CV_16S, 1, 0, ksize=3)
                gy = cv2.Sobel(data, cv2.CV_16S, 0, 1, ksize=3)
                edge = cv2.convertScaleAbs(cv2.addWeighted(cv2.convertScaleAbs(gx), 0.5,
                                                           cv2.convertScaleAbs(gy), 0.5, 0))
            h0, w0 = edge.shape[:2]
            for s in scales:
                w = max(2, int(round(w0 * s)))
                h = max(2, int(round(h0 * s)))
                tpl = edge if (w == w0 and h == h0) else cv2.resize(edge, (w, h), interpolation=cv2.INTER_AREA)
                self.templates.append((tpl, (w, h)))
                total += 1
        self.cursor = 0
        return total

    def count(self) -> int:
        return len(self.templates)

    def get_next_batch(self, k: int = 2) -> List[Tuple[np.ndarray, Tuple[int, int]]]:
        if not self.templates:
            return []
        k = max(1, min(k, len(self.templates)))
        end = self.cursor + k
        batch = self.templates[self.cursor:end]
        # 轮转
        self.cursor = 0 if end >= len(self.templates) else end
        return batch


class ScannerWorker(QtCore.QThread):
    """模板扫描与无感点击线程。"""

    # 状态文本（用于托盘提示）
    sig_status = QtCore.Signal(str)
    # 命中信号：score, sx, sy（屏幕坐标）
    sig_hit = QtCore.Signal(float, int, int)
    # 错误或日志文本
    sig_log = QtCore.Signal(str)

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._running = False
        self._next_allowed = 0.0
        self._consecutive = 0
        self._logger = get_logger()
        # 模板仓库
        self._tpl_bank = TemplateBank()
        # 已加载模板签名
        self._tpl_loaded_key: str = ""
        
        # 调试和多屏幕支持相关
        self._debug_counter = 0
        self._monitor_info_cache = None
        self._last_monitor_check = 0.0
        # 多屏幕轮询相关
        self._current_polling_monitor = 1
        self._last_polling_switch = 0.0
        self._all_monitors_cache = None
        
        # 解析调试目录（相对路径基于应用目录：exe或主脚本目录）并确保存在
        base_dir = get_app_base_dir()
        if os.path.isabs(self.cfg.debug_image_dir):
            self._debug_dir = self.cfg.debug_image_dir
        else:
            self._debug_dir = os.path.join(base_dir, self.cfg.debug_image_dir)
        if self.cfg.save_debug_images:
            os.makedirs(self._debug_dir, exist_ok=True)

        # 自适应调度器与前台窗口信息
        self._scheduler = AdaptiveScanScheduler(SchedulerConfig(
            scan_mode=getattr(self.cfg, 'scan_mode', 'event'),
            active_scan_interval_ms=getattr(self.cfg, 'active_scan_interval_ms', 120),
            idle_scan_interval_ms=getattr(self.cfg, 'idle_scan_interval_ms', 2000),
            miss_backoff_ms_max=getattr(self.cfg, 'miss_backoff_ms_max', 5000),
            hit_cooldown_ms=getattr(self.cfg, 'hit_cooldown_ms', 4000),
            process_whitelist=list(getattr(self.cfg, 'process_whitelist', ["Code.exe", "Windsurf.exe", "Trae.exe"]))
        ))
        self._fg_hwnd: int = 0
        self._fg_proc: str = ""
        self._hook_handle = None
        # 缓存边缘图大小以便复用
        self._last_edge_shape = (0, 0)
        self._edge_img: np.ndarray | None = None

    # ---------- 公共控制接口 ----------

    def update_config(self, cfg: AppConfig):
        """更新运行配置；模板路径变化会重新加载模板。"""
        self.cfg = cfg
        # 下次循环会使用新的参数，必要时重载模板
        self._load_templates(force=True)
        # 同步自适应调度器配置
        self._scheduler = AdaptiveScanScheduler(SchedulerConfig(
            scan_mode=getattr(self.cfg, 'scan_mode', 'event'),
            active_scan_interval_ms=getattr(self.cfg, 'active_scan_interval_ms', 120),
            idle_scan_interval_ms=getattr(self.cfg, 'idle_scan_interval_ms', 2000),
            miss_backoff_ms_max=getattr(self.cfg, 'miss_backoff_ms_max', 5000),
            hit_cooldown_ms=getattr(self.cfg, 'hit_cooldown_ms', 4000),
            process_whitelist=list(getattr(self.cfg, 'process_whitelist', ["Code.exe", "Windsurf.exe", "Trae.exe"]))
        ))

    def stop(self):
        self._running = False

    # ---------- 核心线程逻辑 ----------

    def run(self):
        self._running = True
        self._consecutive = 0
        self._next_allowed = 0.0
        self._load_templates(force=True)

        # 初始化 mss
        try:
            # 事件：前台窗口变化 -> 更新调度器活跃态
            def _on_fg(hwnd: int, pname: str):
                self._fg_hwnd = int(hwnd)
                self._fg_proc = pname or ""
                self._scheduler.on_foreground_change(self._fg_proc)
            try:
                self._hook_handle = start_foreground_watcher(_on_fg)
            except Exception:
                self._hook_handle = None

            with mss.mss() as sct:
                while self._running:
                    t0 = time.monotonic()
                    try:
                        score, matched = self._scan_once_and_maybe_click(sct)
                        delay_ms = self._scheduler.next_delay_ms()
                        fg = self._fg_proc or "(无前台)"
                        status_msg = f"运行中[{getattr(self.cfg, 'scan_mode', 'event')}] | 前台:{fg} | 匹配:{score:.3f} | 下一次:{delay_ms}ms"
                        self.sig_status.emit(status_msg)
                    except Exception as e:
                        self._logger.exception("扫描异常: %s", e)
                        self.sig_log.emit(f"扫描异常: {e}")

                    # 控制间隔：自适应
                    dt = (time.monotonic() - t0) * 1000.0
                    sleep_ms = max(1, int(self._scheduler.next_delay_ms() - dt))
                    if sleep_ms > 0:
                        time.sleep(sleep_ms / 1000.0)
        except Exception as e:
            self._logger.exception("mss 初始化失败: %s", e)
            self.sig_log.emit(f"mss 初始化失败: {e}")
            self.sig_status.emit("已停止")
        finally:
            try:
                stop_foreground_watcher()
            except Exception:
                pass

    # ---------- 私有工具函数 ----------
    
    def _get_monitor_info(self, sct: mss.mss, force_refresh: bool = False) -> dict:
        """获取显示器信息，带缓存机制。"""
        now = time.monotonic()
        if force_refresh or self._monitor_info_cache is None or (now - self._last_monitor_check) > 5.0:
            mons = sct.monitors
            idx = self.cfg.monitor_index
            if idx < 1 or idx >= len(mons):
                idx = 1
            
            mon = mons[idx]
            self._monitor_info_cache = {
                'monitor': mon,
                'index': idx,
                'total_monitors': len(mons) - 1,  # 减去虚拟显示器
                'virtual_screen': mons[0]  # 虚拟屏幕（所有显示器的联合）
            }
            self._last_monitor_check = now
            
            if self.cfg.debug_mode:
                self._logger.info(f"显示器信息更新: 使用显示器{idx}, 总数{self._monitor_info_cache['total_monitors']}")
                self._logger.info(f"显示器{idx}区域: {mon}")
                self._logger.info(f"虚拟屏幕区域: {mons[0]}")
        
        return self._monitor_info_cache
    
    def _get_all_monitors_info(self, sct: mss.mss, force_refresh: bool = False) -> List[dict]:
        """获取所有显示器信息，用于多屏幕轮询。"""
        now = time.monotonic()
        if force_refresh or self._all_monitors_cache is None or (now - self._last_monitor_check) > 5.0:
            mons = sct.monitors
            self._all_monitors_cache = []
            
            # 跳过虚拟显示器（索引0），从实际显示器开始
            for i in range(1, len(mons)):
                mon_info = {
                    'monitor': mons[i],
                    'index': i,
                    'total_monitors': len(mons) - 1,
                    'virtual_screen': mons[0]
                }
                self._all_monitors_cache.append(mon_info)
            
            if self.cfg.debug_mode:
                self._logger.info(f"所有显示器信息更新: 共{len(self._all_monitors_cache)}个显示器")
                for i, info in enumerate(self._all_monitors_cache):
                    self._logger.info(f"显示器{info['index']}: {info['monitor']}")
        
        return self._all_monitors_cache
    
    def _get_next_polling_monitor(self, sct: mss.mss) -> int:
        """获取下一个要轮询的显示器索引。"""
        now = time.monotonic()
        
        # 检查是否需要切换到下一个显示器
        if (now - self._last_polling_switch) >= (self.cfg.screen_polling_interval_ms / 1000.0):
            all_monitors = self._get_all_monitors_info(sct)
            if all_monitors:
                # 切换到下一个显示器
                current_idx = -1
                for i, info in enumerate(all_monitors):
                    if info['index'] == self._current_polling_monitor:
                        current_idx = i
                        break
                
                # 切换到下一个显示器
                next_idx = (current_idx + 1) % len(all_monitors)
                self._current_polling_monitor = all_monitors[next_idx]['index']
                self._last_polling_switch = now
                
                if self.cfg.debug_mode:
                    self._logger.info(f"多屏幕轮询: 切换到显示器{self._current_polling_monitor}")
        
        return self._current_polling_monitor
    
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
        """保存调试图片。"""
        if not self.cfg.save_debug_images:
            return
        
        self._debug_counter += 1
        timestamp = int(time.time() * 1000)
        filename = f"{prefix}_{timestamp}_{self._debug_counter:04d}.png"
        if extra_info:
            filename = f"{prefix}_{extra_info}_{timestamp}_{self._debug_counter:04d}.png"
        
        filepath = os.path.join(self._debug_dir, filename)
        try:
            cv2.imwrite(filepath, img)
            if self.cfg.debug_mode:
                self._logger.info(f"调试图片已保存: {filepath}")
        except Exception as e:
            self._logger.error(f"保存调试图片失败: {e}")
    
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
        """加载模板到模板仓库（统一边缘域 + 固定尺度金字塔）。"""
        # 组装当前模板签名：多路径 + 固定尺度
        paths: List[str] = []
        if getattr(self.cfg, "template_paths", None):
            paths = [os.path.abspath(p) for p in self.cfg.template_paths if str(p).strip()]
        if not paths:
            # 回退单路径
            paths = [os.path.abspath(self.cfg.template_path)]

        key = "|".join([";".join(paths), "edges=1", "scales=0.9,1.0,1.1"])

        if not force and self._tpl_bank.count() > 0 and self._tpl_loaded_key == key:
            return

        # 重新加载
        self._tpl_bank.clear()
        self._tpl_loaded_key = key

        total_tpl_count = 0
        missing_files: List[str] = []

        # 计算工程根目录，用于资源回退（assets/images）
        proj_root = get_app_base_dir()
        assets_img_dir = os.path.join(proj_root, 'assets', 'images')

        load_list: List[str] = []
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
            load_list.append(load_path)

        total_tpl_count = self._tpl_bank.load_from_paths(load_list)

        # 日志反馈
        if missing_files:
            self.sig_log.emit("以下模板文件不存在: " + "; ".join(missing_files))
        self.sig_log.emit(f"模板已加载，路径数={len(load_list)}，总尺度数={total_tpl_count}")

    def _grab_roi(self, sct: mss.mss) -> Tuple[np.ndarray, int, int]:
        """抓取 ROI 图像，返回 (img, left, top)；left/top 为该 ROI 的屏幕坐标。
        增强版：支持坐标校正、边界检查和调试模式。
        """
        monitor_info = self._get_monitor_info(sct)
        mon = monitor_info['monitor']
        m_left, m_top = mon['left'], mon['top']
        m_width, m_height = mon['width'], mon['height']

        roi: ROI = self.cfg.roi
        
        # 计算ROI的实际坐标
        if roi.w > 0 and roi.h > 0:
            # 使用指定的ROI
            left = m_left + roi.x
            top = m_top + roi.y
            width = roi.w
            height = roi.h
        else:
            # 使用整个显示器
            left = m_left
            top = m_top
            width = m_width
            height = m_height
        
        # 边界检查和校正
        virtual_screen = monitor_info['virtual_screen']
        
        # 确保ROI不超出虚拟屏幕边界
        left = max(virtual_screen['left'], left)
        top = max(virtual_screen['top'], top)
        right = min(virtual_screen['left'] + virtual_screen['width'], left + width)
        bottom = min(virtual_screen['top'] + virtual_screen['height'], top + height)
        
        # 重新计算宽高
        width = max(1, right - left)
        height = max(1, bottom - top)
        
        if self.cfg.debug_mode:
            self._logger.info(f"ROI计算: 显示器{monitor_info['index']}({m_left},{m_top},{m_width}x{m_height})")
            self._logger.info(f"ROI区域: ({left},{top},{width}x{height})")
            if roi.w > 0 and roi.h > 0:
                self._logger.info(f"用户ROI: ({roi.x},{roi.y},{roi.w}x{roi.h})")

        bbox = {"left": left, "top": top, "width": width, "height": height}
        
        try:
            raw = sct.grab(bbox)  # BGRA
            img = np.asarray(raw)
            
            if img.shape[2] == 4:
                img = img[:, :, :3]  # BGR
            
            # 保存原始截图用于调试
            if self.cfg.save_debug_images:
                self._save_debug_image(img, "roi_capture", f"monitor{monitor_info['index']}")
            
            if self.cfg.grayscale:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                
            return img, left, top
            
        except Exception as e:
            self._logger.error(f"截屏失败: {e}, bbox={bbox}")
            if self.cfg.debug_mode:
                self._logger.error(f"显示器信息: {monitor_info}")
            raise

    # --------- 新增：前台窗口仅区域捕获与边缘域匹配 ---------

    def _calc_scan_rect(self) -> Tuple[bool, dict]:
        """计算扫描矩形（屏幕坐标），取配置ROI与前台窗口客户区的交集。"""
        info = get_foreground_window_info()
        if not info.get("valid"):
            self._scheduler.on_foreground_change(None)
            return False, {}
        self._fg_hwnd = int(info["hwnd"])  # 缓存
        self._fg_proc = info.get("process", "")
        self._scheduler.on_foreground_change(self._fg_proc)

        win_rect = info.get("client_rect") or {}
        if not win_rect or win_rect.get("width", 0) <= 1 or win_rect.get("height", 0) <= 1:
            return False, {}

        if getattr(self.cfg, 'bind_roi_to_hwnd', True):
            roi_rect = win_rect
        else:
            # ROI 相对配置显示器转换为屏幕坐标；为简化，使用窗口所在显示器左上为基准
            mon_left, mon_top = 0, 0
            try:
                pt = wintypes.POINT(win_rect['left'], win_rect['top'])
                hmon = user32.MonitorFromPoint(pt, 2)
                class MONITORINFO(ctypes.Structure):
                    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
                user32.GetMonitorInfoW.restype = wintypes.BOOL
                user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
                mi = MONITORINFO(); mi.cbSize = ctypes.sizeof(MONITORINFO)
                if hmon and user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                    mon_left = mi.rcMonitor.left
                    mon_top = mi.rcMonitor.top
            except Exception:
                pass
            r: ROI = self.cfg.roi
            if r.w > 0 and r.h > 0:
                roi_rect = {"left": mon_left + int(r.x), "top": mon_top + int(r.y),
                            "right": mon_left + int(r.x) + int(r.w),
                            "bottom": mon_top + int(r.y) + int(r.h),
                            "width": int(r.w), "height": int(r.h)}
            else:
                roi_rect = win_rect

        L = max(roi_rect['left'], win_rect['left'])
        T = max(roi_rect['top'], win_rect['top'])
        R = min(roi_rect['right'], win_rect['right'])
        B = min(roi_rect['bottom'], win_rect['bottom'])
        if R - L <= 1 or B - T <= 1:
            return False, {}
        rect = {"left": L, "top": T, "right": R, "bottom": B, "width": R - L, "height": B - T}
        return True, rect

    def _capture_rect_blt(self, rect: dict) -> np.ndarray | None:
        """使用 BitBlt 捕获指定屏幕矩形，返回BGR图像；失败返回None。"""
        left, top, width, height = rect['left'], rect['top'], rect['width'], rect['height']
        hdc_screen = user32.GetDC(0)
        if not hdc_screen:
            return None
        try:
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
            bmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
            if not hdc_mem or not bmp:
                return None
            old = gdi32.SelectObject(hdc_mem, bmp)
            SRCCOPY = 0x00CC0020
            ok = gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, left, top, SRCCOPY)
            if not ok:
                gdi32.SelectObject(hdc_mem, old)
                gdi32.DeleteObject(bmp)
                gdi32.DeleteDC(hdc_mem)
                return None
            # 读取位图数据
            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)
                ]
            class BITMAPINFO(ctypes.Structure):
                _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]
            BI_RGB = 0
            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = width
            bmi.bmiHeader.biHeight = -height  # 正向
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 24
            bmi.bmiHeader.biCompression = BI_RGB
            stride = ((width * 3 + 3) // 4) * 4
            buf = (ctypes.c_ubyte * (stride * height))()
            got = gdi32.GetDIBits(hdc_mem, bmp, 0, height, ctypes.byref(buf), ctypes.byref(bmi), 0)
            gdi32.SelectObject(hdc_mem, old)
            gdi32.DeleteObject(bmp)
            gdi32.DeleteDC(hdc_mem)
            if got != height:
                return None
            arr = np.frombuffer(buf, dtype=np.uint8).reshape((height, stride))[:, : width * 3]
            img_bgr = arr.reshape((height, width, 3))
            return img_bgr.copy()
        finally:
            user32.ReleaseDC(0, hdc_screen)

    def _edges_of(self, bgr_or_gray: np.ndarray) -> np.ndarray:
        """得到边缘域图像（复用缓冲以减少分配）。"""
        if bgr_or_gray.ndim == 3:
            gray = cv2.cvtColor(bgr_or_gray, cv2.COLOR_BGR2GRAY)
        else:
            gray = bgr_or_gray
        try:
            edges = cv2.Canny(gray, 60, 180)
        except Exception:
            gx = cv2.Sobel(gray, cv2.CV_16S, 1, 0, ksize=3)
            gy = cv2.Sobel(gray, cv2.CV_16S, 0, 1, ksize=3)
            edges = cv2.convertScaleAbs(cv2.addWeighted(cv2.convertScaleAbs(gx), 0.5,
                                                        cv2.convertScaleAbs(gy), 0.5, 0))
        return edges

    def _match_best(self, img_edges: np.ndarray) -> Tuple[float, Tuple[int, int], Tuple[int, int]]:
        """在边缘域中进行模板匹配，仅匹配少量模板（最多2个）。"""
        best = 0.0
        best_loc = (0, 0)
        best_wh = (0, 0)
        batch = self._tpl_bank.get_next_batch(2)
        if not batch:
            return best, best_loc, best_wh
        for tpl, (tw, th) in batch:
            if img_edges.shape[0] < th or img_edges.shape[1] < tw:
                continue
            res = cv2.matchTemplate(img_edges, tpl, cv2.TM_CCOEFF_NORMED)
            _, maxVal, _, maxLoc = cv2.minMaxLoc(res)
            if maxVal > best:
                best = maxVal
                best_loc = maxLoc
                best_wh = (tw, th)
        return best, best_loc, best_wh

    def _scan_once_and_maybe_click(self, sct: mss.mss) -> Tuple[float, bool]:
        """执行一次扫描并在命中时进行无感点击。返回 (score, matched)。
        - 仅扫描“前台窗口客户区”与“配置ROI”的交集；
        - 优先使用 BitBlt 捕获该区域，失败回退 mss；
        - 在边缘域进行模板匹配；每轮仅处理少量模板以降低占用。
        """
        # 确保模板存在
        if self._tpl_bank.count() == 0:
            self._load_templates(force=True)
            if self._tpl_bank.count() == 0:
                self.sig_status.emit("模板未就绪")
                time.sleep(0.5)
                return 0.0, False

        ok, rect = self._calc_scan_rect()
        if not ok:
            return 0.0, False

        # 捕获
        img_bgr = self._capture_rect_blt(rect)
        if img_bgr is None:
            bbox = {"left": rect['left'], "top": rect['top'], "width": rect['width'], "height": rect['height']}
            try:
                raw = sct.grab(bbox)
                img_bgr = np.asarray(raw)
                if img_bgr.shape[2] == 4:
                    img_bgr = img_bgr[:, :, :3]
            except Exception as e:
                self._logger.error(f"截屏失败: {e}")
                return 0.0, False

        img_edges = self._edges_of(img_bgr)
        score, loc, wh = self._match_best(img_edges)
        threshold = max(0.0, min(1.0, float(self.cfg.threshold)))

        # 调试模式下记录匹配信息
        if self.cfg.debug_mode and score > 0.1:  # 只记录有意义的匹配
            self._logger.info(f"模板匹配: score={score:.3f}, threshold={threshold:.3f}, loc={loc}, size={wh}")

        if score >= threshold:
            self._consecutive += 1
            if self.cfg.debug_mode:
                self._logger.info(f"连续命中: {self._consecutive}/{self.cfg.min_detections}")
        else:
            self._consecutive = 0

        matched = False
        now = time.monotonic()
        if self._consecutive >= max(1, self.cfg.min_detections) and now >= self._next_allowed:
            # 计算点击坐标（屏幕坐标，中心点 + 偏移）
            x, y = loc
            w, h = wh
            
            # 基础坐标计算
            base_cx = rect['left'] + x + w // 2
            base_cy = rect['top'] + y + h // 2
            
            # 应用用户偏移
            offset_cx = base_cx + int(self.cfg.click_offset[0])
            offset_cy = base_cy + int(self.cfg.click_offset[1])
            
            # 应用坐标校正
            final_cx, final_cy = self._apply_coordinate_correction(offset_cx, offset_cy)
            
            # 坐标粗验
            if final_cx < -10000 or final_cx > 100000 or final_cy < -10000 or final_cy > 100000:
                self._consecutive = 0
                return float(score), False
            
            # 保存匹配结果的调试图片
            if self.cfg.save_debug_images:
                debug_img = img_bgr.copy()
                if len(debug_img.shape) == 2:  # 灰度图
                    debug_img = cv2.cvtColor(debug_img, cv2.COLOR_GRAY2BGR)
                # 绘制匹配框和点击点
                cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 255, 0), 2)
                click_x_rel = x + w // 2 + int(self.cfg.click_offset[0])
                click_y_rel = y + h // 2 + int(self.cfg.click_offset[1])
                cv2.circle(debug_img, (click_x_rel, click_y_rel), 5, (0, 0, 255), -1)
                self._save_debug_image(debug_img, "match_result", f"score{score:.3f}")
            
            # 执行点击
            if self.cfg.debug_mode:
                self._logger.info(f"准备点击: 基础({base_cx},{base_cy}) -> 偏移({offset_cx},{offset_cy}) -> 校正({final_cx},{final_cy})")
            
            # 使用配置驱动的点击方法
            ok = post_click_with_config(int(final_cx), int(final_cy), self.cfg)
            
            if ok:
                self._logger.info("已点击: score=%.3f, pos=(%d,%d)", score, final_cx, final_cy)
                self.sig_hit.emit(score, int(final_cx), int(final_cy))
                self._next_allowed = now + max(0.0, float(self.cfg.cooldown_s))
                self._scheduler.on_hit()
                matched = True
            else:
                self._logger.warning("点击发送失败: pos=(%d,%d)", final_cx, final_cy)
                self.sig_log.emit(f"点击发送失败: ({final_cx},{final_cy})")
            
            # 重置累计
            self._consecutive = 0
        else:
            self._scheduler.on_miss()

        return float(score), matched

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
from auto_approve.win_clicker import post_click_with_config


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
        # 模板缓存：(tpl图像, (w,h))，包含所有模板、所有尺度
        self._templates: List[Tuple[np.ndarray, Tuple[int, int]]] = []
        # 已加载模板签名（用于避免重复加载），由多模板路径与关键配置组合而成
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

    # ---------- 公共控制接口 ----------

    def update_config(self, cfg: AppConfig):
        """更新运行配置；模板路径变化会重新加载模板。"""
        self.cfg = cfg
        # 下次循环会使用新的参数，必要时重载模板
        self._load_templates(force=True)

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
            with mss.mss() as sct:
                while self._running:
                    t0 = time.monotonic()
                    try:
                        score = self._scan_once_and_maybe_click(sct)
                        # 显示状态信息，包括多屏幕轮询信息
                        if self.cfg.enable_multi_screen_polling:
                            status_msg = f"运行中(多屏轮询) | 当前屏幕: {self._current_polling_monitor} | 匹配: {score:.3f}"
                        else:
                            status_msg = f"运行中 | 上次匹配: {score:.3f}"
                        self.sig_status.emit(status_msg)
                    except Exception as e:
                        self._logger.exception("扫描异常: %s", e)
                        self.sig_log.emit(f"扫描异常: {e}")

                    # 控制间隔，避免高占用
                    dt = (time.monotonic() - t0) * 1000.0
                    sleep_ms = max(0, int(self.cfg.interval_ms - dt))
                    if sleep_ms > 0:
                        time.sleep(sleep_ms / 1000.0)
        except Exception as e:
            self._logger.exception("mss 初始化失败: %s", e)
            self.sig_log.emit(f"mss 初始化失败: {e}")
            self.sig_status.emit("已停止")

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
        """加载并缓存模板图像（支持多模板、可选多尺度）。"""
        # 组装当前模板签名：多路径 + 灰度/多尺度/倍率
        paths: List[str] = []
        if getattr(self.cfg, "template_paths", None):
            paths = [os.path.abspath(p) for p in self.cfg.template_paths if str(p).strip()]
        if not paths:
            # 回退单路径
            paths = [os.path.abspath(self.cfg.template_path)]

        key = "|".join([
            ";".join(paths),
            f"gray={int(bool(self.cfg.grayscale))}",
            f"ms={int(bool(self.cfg.multi_scale))}",
            f"scales={','.join([f'{s:g}' for s in (self.cfg.scales if self.cfg.multi_scale else (1.0,))])}"
        ])

        if not force and self._templates and self._tpl_loaded_key == key:
            return

        # 重新加载
        self._templates.clear()
        self._tpl_loaded_key = key

        total_tpl_count = 0
        missing_files: List[str] = []

        # 计算工程根目录，用于资源回退（assets/images）
        proj_root = get_app_base_dir()
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

    def _match_best(self, img: np.ndarray) -> Tuple[float, Tuple[int, int], Tuple[int, int]]:
        """在 img 中进行模板匹配，返回 (best_score, best_loc(x,y), best_tpl_size(w,h))。"""
        best = 0.0
        best_loc = (0, 0)
        best_wh = (0, 0)
        if not self._templates:
            return best, best_loc, best_wh

        for tpl, (tw, th) in self._templates:
            if img.shape[0] < th or img.shape[1] < tw:
                continue
            res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
            minVal, maxVal, minLoc, maxLoc = cv2.minMaxLoc(res)
            if maxVal > best:
                best = maxVal
                best_loc = maxLoc
                best_wh = (tw, th)
        return best, best_loc, best_wh

    def _scan_once_and_maybe_click(self, sct: mss.mss) -> float:
        """执行一次扫描并在命中时进行无感点击。返回最佳匹配得分。
        增强版：支持坐标校正、调试模式和多屏幕环境。
        """
        # 确保模板存在
        if not self._templates:
            self._load_templates(force=True)
            if not self._templates:
                self.sig_status.emit("模板未就绪")
                time.sleep(0.5)
                return 0.0

        # 获取显示器信息（支持多屏幕轮询）
        if self.cfg.enable_multi_screen_polling:
            # 多屏幕轮询模式：获取当前要轮询的显示器
            current_monitor_idx = self._get_next_polling_monitor(sct)
            # 临时修改配置中的显示器索引
            original_monitor_idx = self.cfg.monitor_index
            self.cfg.monitor_index = current_monitor_idx
            monitor_info = self._get_monitor_info(sct, force_refresh=True)
            # 恢复原始配置
            self.cfg.monitor_index = original_monitor_idx
        else:
            # 单屏幕模式：使用配置中指定的显示器
            monitor_info = self._get_monitor_info(sct)
        
        img, left, top = self._grab_roi(sct)
        score, loc, wh = self._match_best(img)
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

        now = time.monotonic()
        if self._consecutive >= max(1, self.cfg.min_detections) and now >= self._next_allowed:
            # 计算点击坐标（屏幕坐标，中心点 + 偏移）
            x, y = loc
            w, h = wh
            
            # 基础坐标计算
            base_cx = left + x + w // 2
            base_cy = top + y + h // 2
            
            # 应用用户偏移
            offset_cx = base_cx + int(self.cfg.click_offset[0])
            offset_cy = base_cy + int(self.cfg.click_offset[1])
            
            # 应用坐标校正
            final_cx, final_cy = self._apply_coordinate_correction(offset_cx, offset_cy)
            
            # 验证坐标有效性
            if not self._validate_coordinates(final_cx, final_cy, monitor_info):
                self._logger.warning(f"点击坐标无效: ({final_cx},{final_cy})")
                self.sig_log.emit(f"点击坐标无效: ({final_cx},{final_cy})")
                self._consecutive = 0
                return float(score)
            
            # 保存匹配结果的调试图片
            if self.cfg.save_debug_images:
                debug_img = img.copy()
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
            else:
                self._logger.warning("点击发送失败: pos=(%d,%d)", final_cx, final_cy)
                self.sig_log.emit(f"点击发送失败: ({final_cx},{final_cy})")
            
            # 重置累计
            self._consecutive = 0

        return float(score)

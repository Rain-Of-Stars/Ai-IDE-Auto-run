# -*- coding: utf-8 -*-
"""
独立扫描进程模块

将扫描功能完全独立为进程，避免UI卡顿：
- 使用multiprocessing.Process实现完全独立的扫描进程
- 通过Queue进行进程间通信
- 支持配置动态更新
- 提供状态监控和错误处理
"""

import os
import sys
import time
import uuid
import pickle
import traceback
import multiprocessing as mp
from typing import Any, Dict, List, Tuple, Optional, Union
import ctypes
from ctypes import wintypes
from dataclasses import dataclass, asdict
from queue import Empty
import numpy as np
import cv2

from PySide6 import QtCore
from PySide6.QtCore import QObject, Signal, QTimer

from auto_approve.config_manager import AppConfig
from auto_approve.logger_manager import get_logger
from auto_approve.win_clicker import post_click_with_config, post_click_in_window_with_config
from capture.capture_manager import CaptureManager
from capture.monitor_utils import get_monitor_info
from utils.win_dpi import set_process_dpi_awareness, get_dpi_info_summary


# 确保Windows平台使用spawn方式启动进程
if sys.platform.startswith('win'):
    mp.set_start_method('spawn', force=True)


@dataclass
class ScannerCommand:
    """扫描器命令"""
    command: str  # 'start', 'stop', 'update_config', 'get_status'
    data: Any = None
    timestamp: float = 0.0


@dataclass
class ScannerStatus:
    """扫描器状态"""
    running: bool = False
    status_text: str = ""
    backend: str = ""
    detail: str = ""
    scan_count: int = 0
    error_message: str = ""
    timestamp: float = 0.0


@dataclass
class ScannerHit:
    """扫描命中结果"""
    score: float
    x: int
    y: int
    timestamp: float


class ScannerProcessSignals(QObject):
    """扫描进程信号类"""
    # 状态更新信号
    status_updated = Signal(object)  # ScannerStatus
    # 命中信号
    hit_detected = Signal(object)   # ScannerHit
    # 日志信号
    log_message = Signal(str)
    # 错误信号
    error_occurred = Signal(str)


def _load_templates_from_paths(template_paths: List[str]) -> List[Tuple[np.ndarray, Tuple[int, int]]]:
    """加载模板图像 - 使用内存模板管理器避免磁盘IO"""
    try:
        # 导入内存模板管理器
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.memory_template_manager import get_template_manager

        # 获取模板管理器并加载模板
        template_manager = get_template_manager()
        template_manager.load_templates(template_paths)

        # 从内存获取模板数据
        templates = template_manager.get_templates(template_paths)

        print(f"从内存加载了 {len(templates)} 个模板")
        return templates

    except Exception as e:
        print(f"内存模板管理器加载失败，回退到传统方式: {e}")

        # 回退到传统的磁盘加载方式
        templates = []
        for path in template_paths:
            try:
                if os.path.exists(path):
                    # 使用cv2.imdecode处理中文路径
                    img_data = np.fromfile(path, dtype=np.uint8)
                    template = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
                    if template is not None:
                        h, w = template.shape[:2]
                        templates.append((template, (w, h)))
            except Exception as e:
                print(f"加载模板失败 {path}: {e}")
        return templates


def _template_matching(roi_img: np.ndarray, templates: List[Tuple[np.ndarray, Tuple[int, int]]], 
                      threshold: float, grayscale: bool) -> Tuple[float, int, int, int, int]:
    """模板匹配：返回分数、最佳位置以及模板宽高（用于中心点击）。"""
    best_score = 0.0
    best_x, best_y = 0, 0
    best_w, best_h = 0, 0
    
    # 转换为灰度图（如果需要）
    if grayscale and len(roi_img.shape) == 3:
        roi_gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
    else:
        roi_gray = roi_img
    
    for template, (tw, th) in templates:
        # 转换模板为灰度图（如果需要）
        if grayscale and len(template.shape) == 3:
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            template_gray = template
        
        # 模板匹配
        result = cv2.matchTemplate(roi_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        
        if max_val > best_score:
            best_score = max_val
            best_x, best_y = max_loc
            best_w, best_h = tw, th
    
    return best_score, best_x, best_y, best_w, best_h


def _scanner_worker_process(command_queue: mp.Queue, status_queue: mp.Queue, 
                           hit_queue: mp.Queue, log_queue: mp.Queue):
    """扫描器工作进程"""
    logger = get_logger()
    logger.info("扫描器工作进程启动")
    
    # 设置 DPI 感知
    set_process_dpi_awareness()
    
    # 进程状态
    running = False
    cfg: Optional[AppConfig] = None
    capture_manager: Optional[CaptureManager] = None
    templates: List[Tuple[np.ndarray, Tuple[int, int]]] = []
    scan_count = 0
    consecutive_clicks = 0
    next_click_allowed = 0.0
    
    def send_status(status_text: str = "", backend: str = "", detail: str = "", error: str = ""):
        """发送状态更新"""
        status = ScannerStatus(
            running=running,
            status_text=status_text,
            backend=backend,
            detail=detail,
            scan_count=scan_count,
            error_message=error,
            timestamp=time.time()
        )
        try:
            status_queue.put_nowait(status)
        except:
            pass
    
    def send_log(message: str):
        """发送日志消息"""
        try:
            log_queue.put_nowait(message)
        except:
            pass
    
    def send_hit(score: float, x: int, y: int):
        """发送命中结果"""
        hit = ScannerHit(score=score, x=x, y=y, timestamp=time.time())
        try:
            hit_queue.put_nowait(hit)
        except:
            pass
    
    def init_capture_manager():
        """初始化捕获管理器（适配新版 CaptureManager API）"""
        nonlocal capture_manager
        try:
            if cfg is None:
                return False

            # 创建管理器并配置参数
            capture_manager = CaptureManager()
            fps = int(getattr(cfg, 'fps_max', getattr(cfg, 'target_fps', 30)))
            include_cursor = bool(getattr(cfg, 'include_cursor', False))
            # 根据模式分别读取边框开关（兼容旧字段）
            use_monitor = bool(getattr(cfg, 'use_monitor', False))
            border_required = bool(
                getattr(cfg, 'screen_border_required' if use_monitor else 'window_border_required',
                        getattr(cfg, 'border_required', False))
            )
            restore_minimized = bool(getattr(cfg, 'restore_minimized_after_capture', False))
            capture_manager.configure(
                fps=fps,
                include_cursor=include_cursor,
                border_required=border_required,
                restore_minimized=restore_minimized
            )
            if use_monitor:
                # 打开显示器捕获（monitor_index 按 0 基准处理）
                monitor_index = int(getattr(cfg, 'monitor_index', 0))
                if not capture_manager.open_monitor(monitor_index):
                    send_log("显示器捕获初始化失败")
                    return False
            else:
                # 选择目标窗口：优先 hwnd，其次标题，再次进程名
                target_hwnd = int(getattr(cfg, 'target_hwnd', 0))
                target_title = getattr(cfg, 'target_window_title', '') or getattr(cfg, 'window_title', '')
                partial = bool(getattr(cfg, 'window_title_partial_match', True))
                target_proc = getattr(cfg, 'target_process', '')

                opened = False
                if target_hwnd > 0:
                    opened = capture_manager.open_window(target_hwnd)
                elif target_title:
                    opened = capture_manager.open_window(target_title, partial_match=partial)
                elif target_proc:
                    opened = capture_manager.open_window(target_proc, partial_match=True)

                if not opened:
                    send_log("窗口捕获初始化失败：请检查 target_hwnd/target_window_title/target_process 配置")
                    return False

            return True
        except Exception as e:
            send_log(f"捕获管理器初始化异常: {e}")
            return False

    def cleanup_capture_manager():
        """清理捕获管理器（新版使用 close）"""
        nonlocal capture_manager
        if capture_manager:
            try:
                capture_manager.close()
            except Exception as e:
                send_log(f"清理捕获管理器异常: {e}")
            finally:
                capture_manager = None

    def load_templates():
        """加载模板"""
        nonlocal templates
        if cfg is None:
            return
        
        template_paths = getattr(cfg, 'template_paths', [])
        templates = _load_templates_from_paths(template_paths)
        send_log(f"加载了 {len(templates)} 个模板")
    
    def apply_roi_to_image(img: np.ndarray) -> Tuple[np.ndarray, int, int]:
        """应用ROI到图像"""
        if cfg is None:
            return img, 0, 0
        
        roi = getattr(cfg, 'roi', None)
        h, w = img.shape[:2]

        # 兼容多种ROI格式：
        # - dataclass ROI(x,y,w,h)
        # - dict {left, top, right, bottom}
        # - 序列 [left, top, right, bottom]
        if roi is None:
            return img, 0, 0

        left = top = 0
        right = w
        bottom = h
        try:
            if hasattr(roi, 'x') and hasattr(roi, 'y') and hasattr(roi, 'w') and hasattr(roi, 'h'):
                # dataclass ROI
                left = int(getattr(roi, 'x', 0))
                top = int(getattr(roi, 'y', 0))
                rw = int(getattr(roi, 'w', 0))
                rh = int(getattr(roi, 'h', 0))
                right = left + (rw if rw > 0 else (w - left))
                bottom = top + (rh if rh > 0 else (h - top))
            elif isinstance(roi, dict):
                left = int(roi.get('left', 0))
                top = int(roi.get('top', 0))
                right = int(roi.get('right', w))
                bottom = int(roi.get('bottom', h))
            elif isinstance(roi, (list, tuple)) and len(roi) == 4:
                left, top, right, bottom = map(int, roi)
            else:
                # 未知格式，使用全图
                return img, 0, 0
        except Exception:
            # 解析失败，使用全图
            return img, 0, 0

        # 边界裁剪
        left = max(0, min(left, w))
        top = max(0, min(top, h))
        right = max(left, min(right, w))
        bottom = max(top, min(bottom, h))

        roi_img = img[top:bottom, left:right]
        return roi_img, left, top

    # --- 坐标换算辅助（WGC窗口内容像素 -> 客户端坐标） ---
    class _POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class _RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    _user32 = ctypes.WinDLL('user32', use_last_error=True)
    _user32.GetClientRect.restype = wintypes.BOOL
    _user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(_RECT)]

    def _get_client_size(hwnd: int) -> Tuple[int, int]:
        """读取窗口客户区宽高，失败返回(0,0)。"""
        try:
            rc = _RECT()
            if _user32.GetClientRect(hwnd, ctypes.byref(rc)):
                return int(rc.right - rc.left), int(rc.bottom - rc.top)
        except Exception:
            pass
        return 0, 0

    def _scale_capture_to_client(x: float, y: float, stats: Dict[str, Any], hwnd: int) -> Tuple[int, int]:
        """将以WGC内容像素计的坐标缩放到窗口客户区坐标，避免缩放错位。"""
        try:
            content_size = stats.get('content_size')  # (w,h) 或 None
            if not content_size or not isinstance(content_size, (list, tuple)):
                return int(round(x)), int(round(y))
            cw, ch = int(content_size[0] or 0), int(content_size[1] or 0)
            if cw <= 0 or ch <= 0:
                return int(round(x)), int(round(y))
            gw, gh = _get_client_size(hwnd)
            if gw <= 0 or gh <= 0:
                return int(round(x)), int(round(y))
            sx = gw / cw
            sy = gh / ch
            return int(round(x * sx)), int(round(y * sy))
        except Exception:
            return int(round(x)), int(round(y))

    def scan_and_maybe_click() -> float:
        """执行扫描和点击"""
        nonlocal scan_count, consecutive_clicks, next_click_allowed
        
        if not templates or not capture_manager or cfg is None:
            return 0.0
        
        # 捕获帧
        restore_after = getattr(cfg, 'restore_minimized_after_capture', False)
        img = capture_manager.capture_frame(restore_after_capture=restore_after)
        
        if img is None:
            return 0.0
        
        # 应用ROI
        roi_img, roi_left, roi_top = apply_roi_to_image(img)
        
        # 模板匹配
        score, match_x, match_y, tpl_w, tpl_h = _template_matching(
            roi_img, templates, cfg.threshold, cfg.grayscale
        )
        
        scan_count += 1
        
        # 检查是否命中
        if score >= cfg.threshold:
            # 计算候选坐标（以ROI左上为基准，点选模板中心）
            raw_x = roi_left + match_x + (tpl_w // 2) + cfg.click_offset[0]
            raw_y = roi_top + match_y + (tpl_h // 2) + cfg.click_offset[1]

            # 判断捕获模式
            stats = capture_manager.get_stats() if capture_manager else {}
            target_hwnd = stats.get('target_hwnd')

            # 点击控制逻辑
            current_time = time.time()
            if current_time >= next_click_allowed:
                try:
                    if target_hwnd:
                        # 窗口捕获：根据内容尺寸与客户区尺寸做自适应缩放，确保精准点击
                        stats = capture_manager.get_stats() if capture_manager else {}
                        cx, cy = _scale_capture_to_client(raw_x, raw_y, stats, int(target_hwnd))
                        success = post_click_in_window_with_config(int(target_hwnd), int(cx), int(cy), cfg)
                        click_log_pos = f"client({cx},{cy}) hwnd={target_hwnd}"
                    else:
                        # 显示器捕获：raw_x/raw_y 是屏幕坐标
                        success = post_click_with_config(int(raw_x), int(raw_y), cfg)
                        click_log_pos = f"screen({raw_x},{raw_y})"

                    if success:
                        consecutive_clicks += 1
                        # 发送命中信号（统一传屏幕坐标更直观）
                        send_hit(score, int(raw_x), int(raw_y))

                        # 计算下次点击时间（容错：若无 click_delay_ms 则使用 cooldown_s）
                        base_delay = getattr(cfg, 'click_delay_ms', None)
                        if base_delay is None:
                            base_delay = getattr(cfg, 'cooldown_s', 1.0) * 1000.0
                        base_delay = float(base_delay) / 1000.0
                        adaptive_delay = base_delay * (1 + consecutive_clicks * 0.1)
                        next_click_allowed = current_time + adaptive_delay

                        send_log(f"点击成功 {click_log_pos}, 置信度: {score:.3f}")
                    else:
                        send_log(f"点击失败 {click_log_pos}, 置信度: {score:.3f}")

                except Exception as e:
                    send_log(f"点击失败: {e}")
            else:
                send_log(f"点击被限制，等待 {next_click_allowed - current_time:.1f}s")
        else:
            # 重置连续点击计数
            if consecutive_clicks > 0:
                consecutive_clicks = max(0, consecutive_clicks - 1)
        
        return score
    
    # 主循环
    try:
        while True:
            # 处理命令
            try:
                command: ScannerCommand = command_queue.get(timeout=0.01)
                
                if command.command == 'start':
                    if not running:
                        cfg = command.data
                        if init_capture_manager():
                            load_templates()
                            running = True
                            scan_count = 0
                            consecutive_clicks = 0
                            next_click_allowed = 0.0
                            send_status("运行中", "进程扫描", "正在初始化...")
                            send_log("扫描进程已启动")
                        else:
                            send_status("", "", "", "初始化失败")
                
                elif command.command == 'stop':
                    if running:
                        running = False
                        cleanup_capture_manager()
                        send_status("已停止", "", "")
                        send_log("扫描进程已停止")
                
                elif command.command == 'update_config':
                    cfg = command.data
                    if running:
                        cleanup_capture_manager()
                        if init_capture_manager():
                            load_templates()
                            send_log("配置已更新")
                        else:
                            running = False
                            send_status("", "", "", "配置更新失败")
                
                elif command.command == 'exit':
                    break
                    
            except Empty:
                pass
            except Exception as e:
                send_log(f"命令处理异常: {e}")
            
            # 执行扫描
            if running:
                try:
                    score = scan_and_maybe_click()
                    
                    # 更新状态
                    backend = "WGC 窗口捕获" if not getattr(cfg, 'use_monitor', False) else "WGC 显示器捕获"
                    detail = f"上次匹配: {score:.3f}"
                    send_status("运行中", backend, detail)
                    
                except Exception as e:
                    send_log(f"扫描异常: {e}")
                    logger.exception("扫描异常")
                
                # 间隔控制
                if cfg:
                    time.sleep(cfg.interval_ms / 1000.0)
            else:
                time.sleep(0.1)  # 空闲时降低CPU使用
                
    except KeyboardInterrupt:
        send_log("扫描进程被中断")
    except Exception as e:
        send_log(f"扫描进程异常: {e}")
        logger.exception("扫描进程异常")
    finally:
        cleanup_capture_manager()
        send_log("扫描进程退出")


class ScannerProcessManager(QObject):
    """扫描进程管理器"""
    
    def __init__(self):
        super().__init__()
        self._logger = get_logger()
        self.signals = ScannerProcessSignals()
        
        # 进程和队列
        self._process: Optional[mp.Process] = None
        self._command_queue: Optional[mp.Queue] = None
        self._status_queue: Optional[mp.Queue] = None
        self._hit_queue: Optional[mp.Queue] = None
        self._log_queue: Optional[mp.Queue] = None
        
        # 状态轮询定时器
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_queues)
        self._poll_timer.setInterval(16)  # 16ms轮询，约60FPS
        
        # 当前状态
        self._running = False
        self._current_config: Optional[AppConfig] = None
        
        self._logger.info("扫描进程管理器初始化完成")

    def start_scanning(self, cfg: AppConfig) -> bool:
        """启动扫描进程"""
        if self._running:
            self._logger.warning("扫描进程已在运行")
            return True

        try:
            # 创建队列
            self._command_queue = mp.Queue()
            self._status_queue = mp.Queue()
            self._hit_queue = mp.Queue()
            self._log_queue = mp.Queue()

            # 创建进程
            self._process = mp.Process(
                target=_scanner_worker_process,
                args=(self._command_queue, self._status_queue, self._hit_queue, self._log_queue),
                daemon=True
            )

            # 启动进程
            self._process.start()
            self._logger.info(f"扫描进程已启动 (PID: {self._process.pid})")

            # 启动轮询
            self._poll_timer.start()

            # 发送启动命令
            command = ScannerCommand(command='start', data=cfg, timestamp=time.time())
            self._command_queue.put(command)

            self._running = True
            self._current_config = cfg

            return True

        except Exception as e:
            self._logger.error(f"启动扫描进程失败: {e}")
            self._cleanup_process()
            return False

    def stop_scanning(self) -> bool:
        """停止扫描进程"""
        if not self._running:
            self._logger.warning("扫描进程未在运行")
            return True

        try:
            # 发送停止命令
            if self._command_queue:
                command = ScannerCommand(command='stop', timestamp=time.time())
                self._command_queue.put(command)

                # 等待一段时间后发送退出命令
                QtCore.QTimer.singleShot(1000, self._send_exit_command)

            return True

        except Exception as e:
            self._logger.error(f"停止扫描进程失败: {e}")
            return False

    def update_config(self, cfg: AppConfig):
        """更新配置"""
        self._current_config = cfg

        if self._running and self._command_queue:
            try:
                command = ScannerCommand(command='update_config', data=cfg, timestamp=time.time())
                self._command_queue.put(command)
                self._logger.info("配置更新命令已发送")
            except Exception as e:
                self._logger.error(f"发送配置更新命令失败: {e}")

    def is_running(self) -> bool:
        """检查是否在运行"""
        return self._running and self._process and self._process.is_alive()

    def _send_exit_command(self):
        """发送退出命令"""
        if self._command_queue:
            try:
                command = ScannerCommand(command='exit', timestamp=time.time())
                self._command_queue.put(command)
            except:
                pass

        # 延迟清理
        QtCore.QTimer.singleShot(2000, self._cleanup_process)

    def _cleanup_process(self):
        """清理进程资源"""
        self._running = False

        # 停止轮询
        if self._poll_timer.isActive():
            self._poll_timer.stop()

        # 终止进程
        if self._process and self._process.is_alive():
            try:
                self._process.terminate()
                self._process.join(timeout=3)

                if self._process.is_alive():
                    self._logger.warning("强制杀死扫描进程")
                    self._process.kill()
                    self._process.join(timeout=1)

            except Exception as e:
                self._logger.error(f"清理扫描进程失败: {e}")

        # 清理队列
        self._command_queue = None
        self._status_queue = None
        self._hit_queue = None
        self._log_queue = None
        self._process = None

        self._logger.info("扫描进程资源已清理")

    def _poll_queues(self):
        """轮询队列获取结果"""
        try:
            # 处理状态更新
            while self._status_queue:
                try:
                    status: ScannerStatus = self._status_queue.get_nowait()
                    self.signals.status_updated.emit(status)
                except Empty:
                    break
                except Exception as e:
                    self._logger.debug(f"处理状态更新失败: {e}")
                    break

            # 处理命中结果
            while self._hit_queue:
                try:
                    hit: ScannerHit = self._hit_queue.get_nowait()
                    self.signals.hit_detected.emit(hit)
                except Empty:
                    break
                except Exception as e:
                    self._logger.debug(f"处理命中结果失败: {e}")
                    break

            # 处理日志消息
            while self._log_queue:
                try:
                    log_msg: str = self._log_queue.get_nowait()
                    self.signals.log_message.emit(log_msg)
                except Empty:
                    break
                except Exception as e:
                    self._logger.debug(f"处理日志消息失败: {e}")
                    break

        except Exception as e:
            self._logger.error(f"轮询队列异常: {e}")

    def cleanup(self):
        """清理资源"""
        if self._running:
            self.stop_scanning()

        # 等待清理完成
        QtCore.QTimer.singleShot(3000, self._cleanup_process)


# 全局扫描进程管理器实例
_global_scanner_manager: Optional[ScannerProcessManager] = None


def get_global_scanner_manager() -> ScannerProcessManager:
    """获取全局扫描进程管理器实例"""
    global _global_scanner_manager
    if _global_scanner_manager is None:
        _global_scanner_manager = ScannerProcessManager()
    return _global_scanner_manager

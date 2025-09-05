# -*- coding: utf-8 -*-
"""
捕获/识别两级Worker（QObject+QThread）骨架

目标与约束：
- CaptureWorker：仅负责WGC/显示器抓帧，线程内用QTimer定时抓取；
- VisionWorker：仅负责ROI裁剪与模板匹配，线程内用QTimer取“最新帧”并异步投递CPU任务；
- 二者禁止创建或触碰任何QWidget/QPixmap；
- 与UI通信仅通过Signal/Slot，传递numpy.ndarray或轻量字典；
- 输出到有界最新帧队列（长度≤2），UI只消费最新结果以避免延迟累积。
"""
from __future__ import annotations
from typing import Optional, Tuple, Dict, Any, List
import time
import numpy as np

from PySide6 import QtCore

from auto_approve.logger_manager import get_logger
from auto_approve.config_manager import AppConfig
from capture.capture_manager import CaptureManager
from utils.bounded_latest_queue import BoundedLatestQueue

# 复用已有的模板匹配实现，避免重复逻辑
from auto_approve.scanner_worker_refactored import template_matching_task
from workers.cpu_tasks import submit_cpu


class CaptureWorker(QtCore.QObject):
    """屏幕/窗口抓帧Worker（运行于独立QThread）。"""

    # 抓到新帧信号：传递numpy.ndarray（BGR）
    sig_frame = QtCore.Signal(object)
    # 状态/日志：仅文本
    sig_status = QtCore.Signal(str)
    sig_log = QtCore.Signal(str)
    # 错误通知
    sig_error = QtCore.Signal(str)

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self._logger = get_logger()
        self._cfg = cfg
        self._cap: Optional[CaptureManager] = None
        self._timer: Optional[QtCore.QTimer] = None
        self._running = False

    @QtCore.Slot()
    def start(self):
        """在工作线程启动抓帧定时器。"""
        try:
            self._cap = CaptureManager()
            # 读取配置：窗口/显示器、FPS、光标等
            fps = int(getattr(self._cfg, 'fps_max', getattr(self._cfg, 'target_fps', 30)))
            include_cursor = bool(getattr(self._cfg, 'include_cursor', False))
            use_monitor = bool(getattr(self._cfg, 'use_monitor', False))
            border_required = bool(
                getattr(self._cfg, 'screen_border_required' if use_monitor else 'window_border_required',
                        getattr(self._cfg, 'border_required', False))
            )
            restore_minimized = bool(getattr(self._cfg, 'restore_minimized_after_capture', False))

            self._cap.configure(
                fps=fps,
                include_cursor=include_cursor,
                border_required=border_required,
                restore_minimized=restore_minimized,
            )

            opened = False
            if use_monitor:
                monitor_index = int(getattr(self._cfg, 'monitor_index', 0))
                opened = self._cap.open_monitor(monitor_index)
            else:
                target_hwnd = int(getattr(self._cfg, 'target_hwnd', 0))
                target_title = getattr(self._cfg, 'target_window_title', '') or getattr(self._cfg, 'window_title', '')
                partial = bool(getattr(self._cfg, 'window_title_partial_match', True))
                if target_hwnd > 0:
                    opened = self._cap.open_window(target_hwnd, async_init=True, timeout=3.0)
                elif target_title:
                    opened = self._cap.open_window(target_title, partial_match=partial, async_init=True, timeout=3.0)
                else:
                    opened = False

            if not opened:
                self.sig_error.emit("捕获初始化失败：未找到有效目标")
                return

            interval_ms = max(16, int(round(1000.0 / max(1, min(fps, 60)))))
            self._timer = QtCore.QTimer(self)
            self._timer.timeout.connect(self._on_tick)
            self._timer.start(interval_ms)
            self._running = True
            self.sig_status.emit(f"捕获已启动 | FPS≤{fps}")
        except Exception as e:
            self.sig_error.emit(f"捕获启动异常: {e}")

    @QtCore.Slot()
    def stop(self):
        """停止抓帧并清理资源。"""
        self._running = False
        try:
            if self._timer and self._timer.isActive():
                self._timer.stop()
        except Exception:
            pass
        try:
            if self._cap:
                self._cap.close()
        except Exception:
            pass
        finally:
            self._cap = None
            self._timer = None
            self.sig_status.emit("捕获已停止")

    @QtCore.Slot(object)
    def update_config(self, cfg: AppConfig):
        """线程安全配置更新。"""
        self._cfg = cfg
        # 运行中也可以在下一次tick应用（简化起见直接重启会话）
        if self._running:
            self.stop()
            QtCore.QTimer.singleShot(0, self.start)

    @QtCore.Slot()
    def _on_tick(self):
        """抓帧定时器回调，在工作线程中执行。"""
        if not self._cap:
            return
        try:
            # 优先共享缓存读取；若无则直接抓取
            img = self._cap.get_shared_frame("pipeline_capture", "detection")
            if img is None:
                img = self._cap.capture_frame(restore_after_capture=bool(getattr(self._cfg, 'restore_minimized_after_capture', False)))
            if img is not None:
                self.sig_frame.emit(img)
        except Exception as e:
            self.sig_log.emit(f"抓帧失败: {e}")


class VisionWorker(QtCore.QObject):
    """视觉处理Worker（运行于独立QThread）。

    - 从有限队列取最新帧；
    - 进行ROI裁剪；
    - 将模板匹配任务提交到CPU池；
    - 通过信号将结果回传主线程。
    """

    sig_result = QtCore.Signal(object)  # 结果字典：{match_found, confidence, click_x, click_y, ...}
    sig_status = QtCore.Signal(str)
    sig_log = QtCore.Signal(str)
    sig_error = QtCore.Signal(str)

    def __init__(self, cfg: AppConfig, frame_queue: BoundedLatestQueue, parent=None):
        super().__init__(parent)
        self._logger = get_logger()
        self._cfg = cfg
        self._q = frame_queue
        self._timer: Optional[QtCore.QTimer] = None
        self._running = False

        # 模板缓存（与进程池任务参数共享）
        self._templates: List[Tuple[np.ndarray, Tuple[int, int]]] = []

    @QtCore.Slot()
    def start(self):
        """启动取帧与识别循环（基于QTimer）。"""
        try:
            self._timer = QtCore.QTimer(self)
            self._timer.timeout.connect(self._on_tick)
            # 取帧频率可与UI刷新解耦，这里先取33ms（约30FPS）
            self._timer.start(33)
            self._running = True
            self.sig_status.emit("识别已启动")
        except Exception as e:
            self.sig_error.emit(f"识别启动异常: {e}")

    @QtCore.Slot()
    def stop(self):
        """停止识别循环。"""
        self._running = False
        try:
            if self._timer and self._timer.isActive():
                self._timer.stop()
        except Exception:
            pass
        finally:
            self._timer = None
            self.sig_status.emit("识别已停止")

    @QtCore.Slot(object)
    def update_config(self, cfg: AppConfig):
        """线程安全配置更新。"""
        self._cfg = cfg
        # 模板变化时重新加载
        QtCore.QTimer.singleShot(0, self._ensure_templates_loaded)

    @QtCore.Slot()
    def _on_tick(self):
        """识别周期：取最新帧→裁剪ROI→提交CPU任务。"""
        got, frame = self._q.get_latest()
        if not got or frame is None:
            return

        # 延迟加载模板
        if not self._templates:
            self._ensure_templates_loaded()
            if not self._templates:
                return

        # 裁剪ROI
        roi_img, roi_left, roi_top = self._apply_roi(frame)

        # 组装匹配参数，提交CPU任务（进程池，避免GIL阻塞）
        params = {
            'roi_img': roi_img,
            'templates': self._templates,
            'threshold': float(getattr(self._cfg, 'threshold', 0.88)),
            'grayscale': bool(getattr(self._cfg, 'grayscale', True)),
            'roi_offset': (roi_left, roi_top),
            'click_offset': tuple(getattr(self._cfg, 'click_offset', (0, 0))),
            'task_id': f"vision_{int(time.time()*1000)}"
        }

        def on_ok(task_id: str, result: Dict[str, Any]):
            # 直接透传结果给UI线程
            self.sig_result.emit(result)

        def on_err(task_id: str, err: str, exc: Exception):
            self.sig_log.emit(f"识别失败: {err}")

        submit_cpu(template_matching_task, args=(params,), on_success=on_ok, on_error=on_err)

    def _ensure_templates_loaded(self):
        """加载模板到内存（走内存模板管理，避免重复IO）。"""
        try:
            from utils.memory_template_manager import get_template_manager
            tm = get_template_manager()
            paths = list(getattr(self._cfg, 'template_paths', []) or [])
            if not paths:
                single = getattr(self._cfg, 'template_path', '')
                if single:
                    paths = [single]
            if not paths:
                self.sig_log.emit("模板路径为空")
                return
            tm.load_templates(paths)
            self._templates = tm.get_templates(paths)
            self.sig_log.emit(f"已加载模板{len(self._templates)}个")
        except Exception as e:
            self.sig_log.emit(f"加载模板失败: {e}")

    def _apply_roi(self, img: np.ndarray) -> Tuple[np.ndarray, int, int]:
        """按配置裁剪ROI，返回(roi_img, left, top)。"""
        h, w = img.shape[:2]
        roi = getattr(self._cfg, 'roi', None)
        if roi is None:
            return img, 0, 0

        # 兼容多种表示：dataclass/dict/tuple
        try:
            left = top = 0
            right = w
            bottom = h
            if hasattr(roi, 'x') and hasattr(roi, 'y') and hasattr(roi, 'w') and hasattr(roi, 'h'):
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

            left = max(0, min(left, w))
            top = max(0, min(top, h))
            right = max(left, min(right, w))
            bottom = max(top, min(bottom, h))

            return img[top:bottom, left:right], left, top
        except Exception:
            return img, 0, 0


class ThreadScannerAdapter(QtCore.QObject):
    """线程化扫描适配器：对齐ProcessScanner接口，便于无缝切换。"""

    sig_status = QtCore.Signal(str)
    sig_hit = QtCore.Signal(float, int, int)
    sig_log = QtCore.Signal(str)

    def __init__(self, cfg: AppConfig):
        super().__init__()
        self._logger = get_logger()
        self._cfg = cfg

        # 两级线程与队列
        self._capture_thread: Optional[QtCore.QThread] = None
        self._vision_thread: Optional[QtCore.QThread] = None
        self._frame_q = BoundedLatestQueue(maxlen=2)

        self._cap_worker: Optional[CaptureWorker] = None
        self._vis_worker: Optional[VisionWorker] = None

        self._running = False

    def isRunning(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            self._logger.warning("线程扫描器已在运行")
            return

        # Capture层
        self._capture_thread = QtCore.QThread()
        self._cap_worker = CaptureWorker(self._cfg)
        self._cap_worker.moveToThread(self._capture_thread)
        self._capture_thread.started.connect(self._cap_worker.start)

        # 抓帧→入队
        self._cap_worker.sig_frame.connect(self._frame_q.put)
        self._cap_worker.sig_status.connect(lambda s: self.sig_status.emit(f"捕获 | {s}"))
        self._cap_worker.sig_log.connect(self.sig_log.emit)
        self._cap_worker.sig_error.connect(self.sig_log.emit)

        # Vision层
        self._vision_thread = QtCore.QThread()
        self._vis_worker = VisionWorker(self._cfg, self._frame_q)
        self._vis_worker.moveToThread(self._vision_thread)
        self._vision_thread.started.connect(self._vis_worker.start)

        # 识别→命中
        self._vis_worker.sig_status.connect(lambda s: self.sig_status.emit(f"识别 | {s}"))
        self._vis_worker.sig_log.connect(self.sig_log.emit)
        self._vis_worker.sig_error.connect(self.sig_log.emit)
        self._vis_worker.sig_result.connect(self._on_result)

        # 启动线程
        self._capture_thread.start()
        self._vision_thread.start()
        self._running = True
        self.sig_status.emit("线程扫描器已启动")

    def stop(self):
        if not self._running:
            return
        self._running = False

        # 先停Vision，再停Capture
        try:
            if self._vis_worker:
                QtCore.QMetaObject.invokeMethod(self._vis_worker, "stop", QtCore.Qt.QueuedConnection)
        except Exception:
            pass
        try:
            if self._cap_worker:
                QtCore.QMetaObject.invokeMethod(self._cap_worker, "stop", QtCore.Qt.QueuedConnection)
        except Exception:
            pass

        # 退出线程
        for th in (self._vision_thread, self._capture_thread):
            if th:
                th.quit()
                th.wait(2000)

        self._vision_thread = None
        self._capture_thread = None
        self._vis_worker = None
        self._cap_worker = None
        self.sig_status.emit("线程扫描器已停止")

    def update_config(self, cfg: AppConfig):
        self._cfg = cfg
        if self._vis_worker:
            QtCore.QMetaObject.invokeMethod(self._vis_worker, "update_config", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(object, cfg))
        if self._cap_worker:
            QtCore.QMetaObject.invokeMethod(self._cap_worker, "update_config", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(object, cfg))

    # 兼容接口
    def wait(self, timeout_ms: int = 2000) -> bool:
        # 简化处理：等待线程退出
        start = time.time()
        while self.isRunning() and (time.time() - start) * 1000 < timeout_ms:
            time.sleep(0.05)
        return not self.isRunning()

    def terminate(self):
        self.stop()

    # 结果处理：命中/状态文本
    @QtCore.Slot(object)
    def _on_result(self, result: Dict[str, Any]):
        try:
            score = float(result.get('confidence', 0.0))
            if result.get('match_found'):
                x = int(result.get('click_x', 0))
                y = int(result.get('click_y', 0))
                self.sig_hit.emit(score, x, y)
            # 状态文本（轻量）
            self.sig_status.emit(f"匹配: {score:.3f}")
        except Exception as e:
            self.sig_log.emit(f"结果处理异常: {e}")


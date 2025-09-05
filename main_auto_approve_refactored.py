# -*- coding: utf-8 -*-
"""
自动同意小工具 - 重构版主入口：
- 多线程架构：UI主线程只负责渲染与轻逻辑
- IO密集走QThreadPool，CPU密集走multiprocessing
- 可选接入qasync处理asyncio网络
- 所有UI更新必须在主线程，跨线程/进程通信采用Signal/Queue+QTimer
"""
from __future__ import annotations
import os
import sys
import signal
import warnings
import ctypes
import time
from typing import TYPE_CHECKING, Optional

# 在导入Qt库之前关闭 qt.qpa.window 分类日志
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.window=false")

# 高DPI适配设置
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "RoundPreferFloor")

# 设置DPI感知
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per Monitor V2 DPI Aware
except (AttributeError, OSError):
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # 回退到基础DPI感知
    except (AttributeError, OSError):
        pass

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import QElapsedTimer
from auto_approve.path_utils import get_app_base_dir  # 统一资源基准路径，避免打包/工作目录差异

from auto_approve.config_manager import load_config, save_config, AppConfig
from auto_approve.logger_manager import enable_file_logging, get_logger
from auto_approve.menu_icons import create_menu_icon
from auto_approve.ui_enhancements import UIEnhancementManager
from auto_approve.ui_optimizer import TrayMenuOptimizer, get_performance_throttler
from auto_approve.performance_config import get_performance_config, apply_performance_optimizations
from auto_approve.settings_dialog import SettingsDialog
from auto_approve.gui_responsiveness_manager import get_gui_responsiveness_manager, register_ui_handler, UIUpdateRequest
from auto_approve.gui_performance_monitor import get_gui_performance_monitor, start_gui_monitoring, record_ui_update
from auto_approve.auto_hwnd_updater import AutoHWNDUpdater
# from auto_approve.screen_list_dialog import show_screen_list_dialog  # 右键菜单不再提供入口

# 导入多线程任务模块
from workers.io_tasks import submit_io, get_global_thread_pool, optimize_thread_pool
from workers.cpu_tasks import submit_cpu, get_global_cpu_manager
from workers.async_tasks import setup_qasync_event_loop, submit_async_http, QASYNC_AVAILABLE

if TYPE_CHECKING:
    from auto_approve.scanner_worker import ScannerWorker


class PerformanceTimer:
    """性能计时器，用于监控关键操作耗时"""

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.timer = QElapsedTimer()
        self.logger = get_logger()

    def __enter__(self):
        self.timer.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = self.timer.elapsed()
        if elapsed > 100:  # 超过100ms的操作记录警告
            self.logger.warning(f"性能警告: {self.operation_name} 耗时 {elapsed}ms")
        else:
            self.logger.debug(f"性能监控: {self.operation_name} 耗时 {elapsed}ms")


class PersistentTrayMenu(QtWidgets.QMenu):
    """优化的托盘菜单 - 确保所有操作都在主线程"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.Popup)
        self.logger = get_logger()

    def showEvent(self, event):
        """菜单显示事件 - 性能监控"""
        with PerformanceTimer("菜单显示"):
            super().showEvent(event)


class RefactoredTrayApp(QtWidgets.QSystemTrayIcon):
    """重构后的托盘应用 - 多线程架构"""

    def __init__(self, app: QtWidgets.QApplication):
        # 性能计时器
        self.startup_timer = QElapsedTimer()
        self.startup_timer.start()

        # 初始化图标（基于应用根目录，兼容打包与不同工作目录）
        base_dir = get_app_base_dir()
        self.icon_path = os.path.join(base_dir, "assets", "icons", "icons", "custom_icon.ico")
        if os.path.exists(self.icon_path):
            icon = QtGui.QIcon(self.icon_path)
        else:
            icon = self._create_transparent_icon(16)

        super().__init__(icon)
        self.app = app
        self.setToolTip("AI-IDE-Auto-Run - 初始化中...")

        # 日志和配置
        self.logger = get_logger()
        self.cfg: AppConfig = load_config()
        enable_file_logging(self.cfg.enable_logging)

        # 全局状态中心
        from auto_approve.app_state import get_app_state
        self.state = get_app_state()
        self.state.loggingChanged.connect(self._on_logging_changed)

        # 工作线程和任务管理
        self.worker: Optional["ScannerWorker"] = None
        self.settings_dlg: Optional[SettingsDialog] = None
        
        # 自动窗口句柄更新器
        self.auto_hwnd_updater = AutoHWNDUpdater()
        self.auto_hwnd_updater.hwnd_updated.connect(self._on_hwnd_auto_updated)

        # 初始化多线程基础设施
        self._init_threading_infrastructure()

        # 初始化GUI响应性管理器
        self._init_gui_responsiveness()

        # 创建UI
        self._create_menu()

        # 性能优化
        self._init_performance_optimizations()

        # 记录启动时间
        startup_time = self.startup_timer.elapsed()
        self.logger.info(f"应用启动完成，耗时: {startup_time}ms")

        # 延迟初始化非关键组件
        QtCore.QTimer.singleShot(100, self._delayed_initialization)

    def _init_threading_infrastructure(self):
        """初始化多线程基础设施"""
        with PerformanceTimer("多线程基础设施初始化"):
            # 优化IO线程池 - 启用GUI优先模式
            optimize_thread_pool(cpu_intensive_ratio=0.2, gui_priority=True)  # 主要是IO任务，GUI优先

            # 延迟启动CPU任务管理器 - 避免在初始化时启动进程
            # CPU任务管理器将在需要时才启动
            self._cpu_manager_started = False

            # 设置qasync事件循环（如果可用）
            if QASYNC_AVAILABLE:
                try:
                    self.async_loop = setup_qasync_event_loop(self.app)
                    self.logger.info("qasync事件循环已设置")
                except Exception as e:
                    self.logger.warning(f"qasync设置失败: {e}")
                    self.async_loop = None
            else:
                self.async_loop = None
                self.logger.info("qasync不可用，异步功能已禁用")

    def _init_gui_responsiveness(self):
        """初始化GUI响应性管理器"""
        with PerformanceTimer("GUI响应性管理器初始化"):
            # 获取GUI响应性管理器
            self.gui_manager = get_gui_responsiveness_manager()

            # 注册UI更新处理器
            register_ui_handler('tooltip', self._handle_tooltip_update)
            register_ui_handler('status', self._handle_status_update)
            register_ui_handler('menu', self._handle_menu_update)

            # 连接响应性警告信号
            self.gui_manager.responsiveness_warning.connect(self._on_responsiveness_warning)

            # 初始化GUI性能监控器
            self.performance_monitor = get_gui_performance_monitor()
            self.performance_monitor.performance_alert.connect(self._on_performance_alert)
            self.performance_monitor.responsiveness_changed.connect(self._on_responsiveness_changed)

            # 启动性能监控
            start_gui_monitoring()

            self.logger.info("GUI响应性管理器和性能监控器已初始化")

    def _handle_tooltip_update(self, request: UIUpdateRequest):
        """处理工具提示更新"""
        try:
            tooltip_text = request.data.get('text', '')
            if tooltip_text != self.toolTip():
                self.setToolTip(tooltip_text)
                # 记录UI更新
                record_ui_update()
        except Exception as e:
            self.logger.error(f"更新工具提示失败: {e}")

    def _handle_status_update(self, request: UIUpdateRequest):
        """处理状态更新"""
        try:
            # 这里可以处理状态栏或其他状态显示的更新
            pass
        except Exception as e:
            self.logger.error(f"更新状态失败: {e}")

    def _handle_menu_update(self, request: UIUpdateRequest):
        """处理菜单更新"""
        try:
            # 这里可以处理菜单项的更新
            pass
        except Exception as e:
            self.logger.error(f"更新菜单失败: {e}")

    def _on_responsiveness_warning(self, response_time: float):
        """响应性警告处理"""
        self.logger.warning(f"GUI响应缓慢警告: {response_time:.2f}秒")

    def _on_performance_alert(self, alert_type: str, value: float):
        """性能警告处理"""
        if alert_type == "high_cpu":
            self.logger.warning(f"主线程CPU使用率过高: {value:.1f}%")
        elif alert_type == "high_memory":
            self.logger.warning(f"内存使用过高: {value:.1f}MB")
        elif alert_type == "slow_response":
            self.logger.warning(f"GUI响应时间过长: {value:.1f}ms")
        elif alert_type == "high_latency":
            self.logger.warning(f"事件循环延迟过高: {value:.1f}ms")

    def _on_responsiveness_changed(self, is_responsive: bool):
        """响应性状态变化处理"""
        if not is_responsive:
            self.logger.warning("GUI响应性下降")
            # 可以在这里触发自动优化措施
        else:
            self.logger.info("GUI响应性恢复")

    def _create_menu(self):
        """创建托盘菜单 - 确保在主线程执行"""
        with PerformanceTimer("菜单创建"):
            self.menu = PersistentTrayMenu()
            self.menu.setObjectName("TrayMenu")

            # 状态显示
            self.act_status = QtGui.QAction("状态: 未启动")
            self.act_status.setEnabled(False)
            self.act_backend = QtGui.QAction("后端: -")
            self.act_backend.setEnabled(False)
            self.act_detail = QtGui.QAction("")
            self.act_detail.setEnabled(False)

            # 控制按钮
            self.act_start = QtGui.QAction("开始扫描")
            self.act_stop = QtGui.QAction("停止扫描")

            # 互斥勾选组
            self._run_group = QtGui.QActionGroup(self.menu)
            self._run_group.setExclusive(True)
            self.act_start.setCheckable(True)
            self.act_stop.setCheckable(True)
            self._run_group.addAction(self.act_start)
            self._run_group.addAction(self.act_stop)
            self.act_stop.setChecked(True)  # 默认停止状态

            # 连接信号 - 使用线程安全的方式
            self.act_start.triggered.connect(self._safe_start_scanning)
            self.act_stop.triggered.connect(self._safe_stop_scanning)

            # 添加菜单项
            self.menu.addAction(self.act_status)
            self.menu.addAction(self.act_backend)
            self.menu.addAction(self.act_detail)
            self.menu.addSeparator()
            self.menu.addAction(self.act_start)
            self.menu.addAction(self.act_stop)
            self.menu.addSeparator()

            # 日志开关
            self.act_logging = QtGui.QAction("启用日志到 log.txt")
            self.act_logging.setCheckable(True)
            self.act_logging.setChecked(self.state.enable_logging)
            self.act_logging.triggered.connect(self._safe_toggle_logging)
            self.menu.addAction(self.act_logging)

            # 设置和其他功能
            self.act_settings = QtGui.QAction("设置…")
            self.act_settings.triggered.connect(self._safe_open_settings)
            self.menu.addAction(self.act_settings)

            self.menu.addSeparator()
            self.act_quit = QtGui.QAction("退出")
            self.act_quit.triggered.connect(self._safe_quit)
            self.menu.addAction(self.act_quit)

            self.setContextMenu(self.menu)

            # 托盘图标事件
            self.activated.connect(self._on_activated)

    def _init_performance_optimizations(self):
        """初始化性能优化"""
        with PerformanceTimer("性能优化初始化"):
            # 状态缓存，避免重复更新
            self._cached_status = ""
            self._cached_backend = ""
            self._cached_detail = ""

            # UI更新节流
            self._last_tooltip_update = 0.0
            self._tooltip_update_interval = 2.0  # 每2秒最多更新一次

            # UI优化器
            self._ui_optimizer = TrayMenuOptimizer(self)

            # 应用性能优化设置
            apply_performance_optimizations()

    def _delayed_initialization(self):
        """延迟初始化非关键组件"""
        with PerformanceTimer("延迟初始化"):
            # 创建透明图标用于通知
            self._transparent_icon = self._create_transparent_icon(16)
            self._toast_tray = QtWidgets.QSystemTrayIcon(self._transparent_icon)
            self._toast_tray.setVisible(False)

            # 异步加载图标
            self._load_menu_icons_async()

            # 更新工具提示
            self.setToolTip("AI-IDE-Auto-Run - 就绪")

            # 延迟启动CPU任务管理器 - 在主线程空闲时启动
            QtCore.QTimer.singleShot(500, self._start_cpu_manager)

            # 根据配置：启动后自动开始扫描（修复“启动后自动开始扫描”开关失效）
            try:
                if getattr(self.cfg, 'auto_start_scan', False):
                    self.logger.info("检测到 auto_start_scan=True，启动应用后自动开始扫描")
                    # 放到下一个事件循环，避免阻塞初始化
                    QtCore.QTimer.singleShot(1000, self.start_scanning)  # 延迟到CPU管理器启动后
            except Exception as e:
                self.logger.warning(f"自动开始扫描触发失败: {e}")

    def _start_cpu_manager(self):
        """延迟启动CPU任务管理器"""
        if not self._cpu_manager_started:
            try:
                with PerformanceTimer("CPU任务管理器启动"):
                    cpu_manager = get_global_cpu_manager()
                    cpu_manager.start()
                    self._cpu_manager_started = True
                    self.logger.info("CPU任务管理器已延迟启动")
            except Exception as e:
                self.logger.error(f"启动CPU任务管理器失败: {e}")


    def _load_menu_icons_async(self):
        """异步加载菜单图标 - 避免阻塞UI"""
        def load_icons_task():
            """IO任务：加载图标文件"""
            try:
                icons = {}
                # 使用应用根目录解析资源路径，增强健壮性
                base_dir = get_app_base_dir()
                icon_dir = os.path.join(base_dir, "assets", "icons")

                # 加载各种图标
                icon_files = {
                    'start': 'play.png',
                    'stop': 'stop.png',
                    'settings': 'settings.png',
                    'log': 'log.png',
                    'quit': 'exit.png'
                }

                for name, filename in icon_files.items():
                    icon_path = os.path.join(icon_dir, filename)
                    if os.path.exists(icon_path):
                        icons[name] = QtGui.QIcon(icon_path)

                return icons
            except Exception as e:
                return {'error': str(e)}

        def on_icons_loaded(task_id: str, result):
            """图标加载完成回调 - 在主线程执行"""
            if 'error' in result:
                self.logger.warning(f"图标加载失败: {result['error']}")
                return

            # 应用图标到菜单项
            if 'start' in result:
                self.act_start.setIcon(result['start'])
            if 'stop' in result:
                self.act_stop.setIcon(result['stop'])
            if 'settings' in result:
                self.act_settings.setIcon(result['settings'])
            if 'log' in result:
                self.act_logging.setIcon(result['log'])
            if 'quit' in result:
                self.act_quit.setIcon(result['quit'])

            self.logger.debug("菜单图标加载完成")

        def on_icons_error(task_id: str, error_msg: str, exception):
            """图标加载失败回调"""
            self.logger.warning(f"图标加载失败: {error_msg}")

        # 提交IO任务
        from workers.io_tasks import IOTaskBase

        class IconLoadTask(IOTaskBase):
            def execute(self):
                return load_icons_task()

        task = IconLoadTask("load_menu_icons")
        submit_io(task, on_icons_loaded, on_icons_error)

    # ==================== 线程安全的操作方法 ====================

    def _safe_start_scanning(self):
        """线程安全的开始扫描"""
        QtCore.QTimer.singleShot(0, self.start_scanning)

    def _safe_stop_scanning(self):
        """线程安全的停止扫描"""
        QtCore.QTimer.singleShot(0, self.stop_scanning)

    def _safe_toggle_logging(self):
        """线程安全的切换日志"""
        QtCore.QTimer.singleShot(0, self.toggle_logging)

    def _safe_open_settings(self):
        """线程安全的打开设置"""
        QtCore.QTimer.singleShot(0, self.open_settings)

    def _safe_show_screen_list(self):
        """线程安全的显示屏幕列表"""
        QtCore.QTimer.singleShot(0, self._show_screen_list)

    def _safe_quit(self):
        """线程安全的退出"""
        QtCore.QTimer.singleShot(0, self.quit)

    # ==================== 核心业务逻辑 ====================

    def start_scanning(self):
        """开始扫描 - 异步启动避免阻塞GUI"""
        if self.worker and self.worker.isRunning():
            self.logger.warning("扫描已在运行中")
            return

        # 立即更新UI状态，给用户反馈
        self.act_start.setChecked(True)
        self.act_stop.setChecked(False)
        self._update_status("启动中", "进程", "正在创建扫描进程...")

        # 异步启动扫描进程，避免阻塞GUI
        QtCore.QTimer.singleShot(0, self._async_start_scanning)

    def _async_start_scanning(self):
        """异步启动扫描进程的实际实现"""
        try:
            with PerformanceTimer("异步启动扫描进程"):
                # 选择扫描后端：默认进程版；设置环境变量 SCANNER_BACKEND=thread 可启用线程版
                backend_env = os.environ.get('SCANNER_BACKEND', '').strip().lower()
                if backend_env == 'thread':
                    from auto_approve.pipeline_workers import ThreadScannerAdapter as _Scanner
                    backend_name = '线程'
                else:
                    # 修正：进程后端应导入 ProcessScannerWorker（ScannerProcessAdapter 的子类）
                    from auto_approve.scanner_process_adapter import ProcessScannerWorker as _Scanner
                    backend_name = '进程'

                self.logger.info("创建扫描器实例...")
                # 创建新的扫描器实例（按后端类型）
                self.worker = _Scanner(self.cfg)

                # 连接信号
                self.worker.sig_status.connect(self._on_status_update)
                self.worker.sig_hit.connect(self._on_hit_detected)
                self.worker.sig_log.connect(self._on_log_message)

                self.logger.info("启动扫描器...")
                # 启动扫描器
                self.worker.start()

                # 设置启动超时检查（增加到30秒）
                self._start_timeout_timer = QtCore.QTimer()
                self._start_timeout_timer.setSingleShot(True)
                self._start_timeout_timer.timeout.connect(self._on_start_timeout)
                self._start_timeout_timer.start(30000)  # 30秒超时

                # 设置进度提示定时器
                self._progress_timer = QtCore.QTimer()
                self._progress_timer.timeout.connect(self._update_start_progress)
                self._progress_counter = 0
                self._progress_timer.start(2000)  # 每2秒更新一次进度

                self.logger.info(f"扫描已启动（{backend_name}模式）")

        except Exception as e:
            self.logger.error(f"启动扫描失败: {e}")
            import traceback
            self.logger.debug(f"详细错误: {traceback.format_exc()}")
            self._show_error_notification("启动失败", f"无法启动扫描: {e}")

            # 恢复UI状态
            self.act_start.setChecked(False)
            self.act_stop.setChecked(True)
            self._update_status("启动失败", "-", f"错误: {e}")

    def _update_start_progress(self):
        """更新启动进度提示"""
        self._progress_counter += 1

        progress_messages = [
            "正在创建扫描进程...",
            "正在初始化捕获管理器...",
            "正在配置WGC后端...",
            "正在加载模板文件...",
            "正在启动扫描循环...",
            "即将完成启动..."
        ]

        if self._progress_counter < len(progress_messages):
            message = progress_messages[self._progress_counter]
            self._update_status("启动中", "进程", message)
        else:
            # 超过预期步骤，显示等待信息
            elapsed = self._progress_counter * 2
            self._update_status("启动中", "进程", f"启动中，已等待{elapsed}秒...")

    def _on_start_timeout(self):
        """启动超时处理"""
        self.logger.warning("扫描进程启动超时（30秒）")

        # 停止进度定时器
        if hasattr(self, '_progress_timer') and self._progress_timer.isActive():
            self._progress_timer.stop()

        self._show_error_notification("启动超时", "扫描进程启动超过30秒，建议运行优化工具")

        # 尝试停止并重置
        if self.worker:
            try:
                self.worker.stop()
                self.worker = None
            except:
                pass

        # 恢复UI状态
        self.act_start.setChecked(False)
        self.act_stop.setChecked(True)
        self._update_status("启动超时", "-", "运行 python tools/optimize_scanner_startup.py")

    def stop_scanning(self):
        """停止扫描 - 在主线程执行"""
        with PerformanceTimer("停止扫描"):
            if not self.worker or not self.worker.isRunning():
                self.logger.warning("扫描未在运行")
                return

            try:
                # 停止扫描器（进程版）
                self.worker.stop()
                self.worker.wait(5000)  # 等待5秒

                if self.worker.isRunning():
                    self.logger.warning("扫描进程未能正常停止，强制终止")
                    self.worker.terminate()
                    self.worker.wait(2000)

                # 清理资源
                self.worker.cleanup()
                self.worker = None

                # 更新UI状态
                self.act_start.setChecked(False)
                self.act_stop.setChecked(True)
                self._update_status("已停止", "-", "")

                self.logger.info("扫描已停止（独立进程模式）")

            except Exception as e:
                self.logger.error(f"停止扫描失败: {e}")

    def toggle_logging(self):
        """切换日志开关 - 在主线程执行"""
        with PerformanceTimer("切换日志"):
            try:
                new_state = self.act_logging.isChecked()

                # 更新全局状态（修复方法名：set_enable_logging）
                self.state.set_enable_logging(new_state, persist=True, emit_signal=True)

                # 保存配置（使用IO任务）
                self._save_config_async()

                self.logger.info(f"日志已{'启用' if new_state else '禁用'}")

            except Exception as e:
                self.logger.error(f"切换日志失败: {e}")

    def open_settings(self):
        """打开设置对话框 - 在主线程执行"""
        with PerformanceTimer("打开设置"):
            try:
                if self.settings_dlg is None:
                    # SettingsDialog内部自行加载配置，不能传入AppConfig作为父对象
                    self.settings_dlg = SettingsDialog()
                    self.settings_dlg.saved.connect(self._on_config_saved)

                self.settings_dlg.show()
                self.settings_dlg.raise_()
                self.settings_dlg.activateWindow()

            except Exception as e:
                self.logger.error(f"打开设置失败: {e}")
                self._show_error_notification("设置错误", f"无法打开设置: {e}")

    def _show_screen_list(self):
        """显示屏幕列表 - 在主线程执行"""
        with PerformanceTimer("显示屏幕列表"):
            try:
                show_screen_list_dialog()
            except Exception as e:
                self.logger.error(f"显示屏幕列表失败: {e}")

    def quit(self):
        """退出应用 - 在主线程执行"""
        with PerformanceTimer("应用退出"):
            try:
                # 停止自动窗口句柄更新器
                if self.auto_hwnd_updater.is_running():
                    self.auto_hwnd_updater.stop()
                
                # 停止扫描
                if self.worker and self.worker.isRunning():
                    self.stop_scanning()

                # 清理多线程资源
                self._cleanup_threading_resources()

                # 隐藏托盘图标
                self.setVisible(False)

                # 退出应用
                self.app.quit()

            except Exception as e:
                self.logger.error(f"退出应用失败: {e}")
                # 强制退出
                sys.exit(1)

    def _cleanup_threading_resources(self):
        """清理多线程资源"""
        try:
            # 停止CPU任务管理器（仅在已启动时）
            if getattr(self, '_cpu_manager_started', False):
                cpu_manager = get_global_cpu_manager()
                cpu_manager.stop()

            # 清理IO线程池
            from workers.io_tasks import cleanup_thread_pool
            cleanup_thread_pool()

            # 取消所有异步任务
            if self.async_loop:
                from workers.async_tasks import cancel_all_async_tasks
                cancel_all_async_tasks()

            # 清理扫描进程资源
            from workers.scanner_process import get_global_scanner_manager
            scanner_manager = get_global_scanner_manager()
            scanner_manager.cleanup()

            self.logger.info("多线程和进程资源已清理")

        except Exception as e:
            self.logger.error(f"清理多线程资源失败: {e}")

    # ==================== 信号处理方法 ====================

    def _on_status_update(self, status: str):
        """状态更新处理 - 在主线程执行"""
        # 如果收到状态更新，说明进程启动成功，取消超时定时器和进度定时器
        if hasattr(self, '_start_timeout_timer') and self._start_timeout_timer.isActive():
            self._start_timeout_timer.stop()
            self.logger.info("收到状态更新，取消启动超时定时器")

        if hasattr(self, '_progress_timer') and self._progress_timer.isActive():
            self._progress_timer.stop()
            self.logger.info("收到状态更新，停止进度提示")

        # 解析状态信息
        parts = status.split(" | ")
        if len(parts) >= 3:
            main_status = parts[0]
            backend = parts[1].replace("后端: ", "")
            detail = parts[2].replace("上次匹配: ", "")
            self._update_status(main_status, backend, detail)

    def _on_hit_detected(self, score: float, x: int, y: int):
        """检测到匹配处理 - 在主线程执行"""
        self.logger.info(f"检测到匹配: 置信度={score:.3f}, 位置=({x}, {y})")
        # 发送系统通知（尊重配置开关）
        try:
            self.notify_with_custom_icon(
                "已自动点击", f"score={score:.3f} @ ({x},{y})", self.icon_path, 2500
            )
        except Exception:
            # 兜底，避免通知异常影响主流程
            pass

    def _on_log_message(self, message: str):
        """日志消息处理 - 在主线程执行"""
        # 这里可以添加日志消息的额外处理
        # 例如：显示在状态栏、发送通知等
        pass

    def _on_config_saved(self, new_config: AppConfig):
        """配置保存处理 - 在主线程执行
        需求实现：
        1) 保存后配置立即生效；
        2) 若当前未在扫描，保存后自动开始扫描（无需手动点"开始扫描"）。
        3) 更新自动窗口句柄更新器配置
        """
        self.cfg = new_config
        
        # 更新自动窗口句柄更新器配置
        self.auto_hwnd_updater.set_config(new_config)
        if new_config.auto_update_hwnd_by_process:
            if not self.auto_hwnd_updater.is_running():
                self.auto_hwnd_updater.start()
                self.logger.info("自动窗口句柄更新器已启动")
        else:
            if self.auto_hwnd_updater.is_running():
                self.auto_hwnd_updater.stop()
                self.logger.info("自动窗口句柄更新器已停止")

        # 如果扫描器正在运行，直接热更新配置
        if self.worker and self.worker.isRunning():
            self.worker.update_config(new_config)
            self.logger.info("配置已更新并已热应用到正在运行的扫描器")
            return

        # 若当前未运行，根据策略自动启动扫描（满足"保存后直接开始抓捕"）
        try:
            # 为满足用户诉求，这里直接在保存后启动；使用单Shot避免阻塞UI线程
            QtCore.QTimer.singleShot(0, self.start_scanning)
            self.logger.info("配置已更新：当前未运行，已自动启动扫描")
        except Exception as e:
            self.logger.warning(f"保存后自动启动扫描失败: {e}")

    def _on_logging_changed(self, enabled: bool):
        """日志开关变化处理 - 在主线程执行"""
        self.act_logging.setChecked(enabled)
        enable_file_logging(enabled)
        
    def _on_hwnd_auto_updated(self, hwnd: int, process_name: str):
        """自动窗口句柄更新处理"""
        try:
            # 更新配置中的目标HWND
            self.cfg.target_hwnd = hwnd
            
            # 如果扫描器正在运行，更新其配置
            if self.worker and self.worker.isRunning():
                self.worker.update_config(self.cfg)
                self.logger.info(f"自动更新扫描器HWND：{hwnd} (进程: {process_name})")
            else:
                self.logger.info(f"自动更新目标窗口HWND：{hwnd} (进程: {process_name})")
                
            # 显示通知
            self.notify_with_custom_icon(
                "窗口句柄已更新",
                f"检测到进程 {os.path.basename(process_name)}，HWND已更新为 {hwnd}",
                msecs=2000
            )
            
        except Exception as e:
            self.logger.error(f"自动窗口句柄更新处理失败: {e}")

    def _on_activated(self, reason):
        """托盘图标激活处理"""
        if reason == QtWidgets.QSystemTrayIcon.DoubleClick:
            self.open_settings()

    # ==================== 辅助方法 ====================

    def _update_status(self, status: str, backend: str, detail: str):
        """更新状态显示 - 节流优化"""
        current_time = time.time()

        # 检查是否需要更新
        if (status == self._cached_status and
            backend == self._cached_backend and
            detail == self._cached_detail):
            return

        # 对关键状态变化放宽节流：初始化→运行/失败/停止 必须立即更新
        critical_transition = False
        try:
            prev_init = ('初始化' in (self._cached_detail or '')) or ('初始化' in (self._cached_status or ''))
            now_critical = ('已停止' in (status or '')) or ('失败' in (detail or '')) or ('运行' in (status or ''))
            critical_transition = prev_init or now_critical
        except Exception:
            critical_transition = True

        # 节流控制（非关键变化才节流）
        if (not critical_transition) and (current_time - self._last_tooltip_update < self._tooltip_update_interval):
            return

        # 更新缓存
        self._cached_status = status
        self._cached_backend = backend
        self._cached_detail = detail
        self._last_tooltip_update = current_time

        # 更新UI
        self.act_status.setText(f"状态: {status}")
        self.act_backend.setText(f"后端: {backend}")
        self.act_detail.setText(detail)

        # 更新工具提示 - 使用GUI响应性管理器
        tooltip = f"AI-IDE-Auto-Run - {status}"
        if detail:
            tooltip += f"\n{detail}"

        # 使用GUI响应性管理器调度更新
        from auto_approve.gui_responsiveness_manager import schedule_ui_update
        schedule_ui_update(
            widget_id='tray_tooltip',
            update_type='tooltip',
            data={'text': tooltip},
            priority=5 if critical_transition else 3  # 关键状态变化优先级更高
        )

    def _save_config_async(self):
        """异步保存配置"""
        def save_config_task():
            """IO任务：保存配置文件"""
            try:
                save_config(self.cfg)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        def on_config_saved(task_id: str, result):
            """配置保存完成回调"""
            if result.get("success"):
                self.logger.debug("配置保存成功")
            else:
                self.logger.error(f"配置保存失败: {result.get('error')}")

        # 提交IO任务
        from workers.io_tasks import IOTaskBase

        class ConfigSaveTask(IOTaskBase):
            def __init__(self, config):
                super().__init__("save_config")
                self.config = config

            def execute(self):
                save_config(self.config)
                return {"success": True}

        task = ConfigSaveTask(self.cfg)
        submit_io(task, on_config_saved)

    def _show_error_notification(self, title: str, message: str):
        """显示错误通知"""
        try:
            self.showMessage(title, message, QtWidgets.QSystemTrayIcon.Critical, 5000)
        except Exception as e:
            self.logger.error(f"显示通知失败: {e}")

    def notify(self, title: str, message: str,
               icon: QtWidgets.QSystemTrayIcon.MessageIcon = QtWidgets.QSystemTrayIcon.Information,
               msecs: int = 2000):
        """托盘通知封装：根据配置决定是否显示通知。"""
        try:
            if getattr(self.cfg, "enable_notifications", True):
                self.showMessage(title, message, icon, msecs)
        except Exception as e:
            self.logger.debug(f"通知显示失败(忽略): {e}")

    def notify_with_custom_icon(self, title: str, message: str,
                                custom_icon_path: str | None = None,
                                msecs: int = 2000):
        """托盘通知封装：尽量使用自定义图标（若不可用则回退）。"""
        try:
            if not getattr(self.cfg, "enable_notifications", True):
                return
            if custom_icon_path and os.path.exists(custom_icon_path):
                icon = QtGui.QIcon(custom_icon_path)
                self.showMessage(title, message, icon, msecs)
            else:
                self.showMessage(title, message, QtWidgets.QSystemTrayIcon.Information, msecs)
        except Exception as e:
            self.logger.debug(f"自定义通知失败(忽略): {e}")

    def _create_transparent_icon(self, size: int) -> QtGui.QIcon:
        """创建透明图标"""
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtCore.Qt.transparent)
        return QtGui.QIcon(pixmap)


def apply_modern_theme(app: QtWidgets.QApplication):
    """应用现代化主题 - 优化版本"""
    with PerformanceTimer("主题应用"):
        # 统一字体
        font = QtGui.QFont("Microsoft YaHei UI", 10)
        font.setHintingPreference(QtGui.QFont.PreferFullHinting)
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        app.setFont(font)

        # 基础Fusion样式
        app.setStyle("Fusion")
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(45, 45, 48))
        palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor(30, 30, 30))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(45, 45, 48))
        palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor(45, 45, 48))
        palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(47, 128, 237))
        palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)
        app.setPalette(palette)

        # 异步加载QSS样式 - 优先使用轻量级样式
        def load_qss_async():
            # 基于应用根目录定位QSS，避免工作目录变化导致丢失
            base_dir = get_app_base_dir()
            qss_paths = [
                os.path.join(base_dir, "assets", "styles", "minimal.qss"),
                os.path.join(base_dir, "assets", "styles", "modern_flat_lite.qss"),
                os.path.join(base_dir, "assets", "styles", "modern_flat.qss"),
            ]

            for qss_path in qss_paths:
                if os.path.exists(qss_path):
                    try:
                        with open(qss_path, "r", encoding="utf-8") as f:
                            qss_content = f.read()
                            if qss_content.strip():
                                QtCore.QTimer.singleShot(0, lambda content=qss_content: app.setStyleSheet(content))
                                print(f"✓ 已加载样式: {os.path.basename(qss_path)}")
                                return
                    except Exception as e:
                        print(f"✗ QSS样式加载失败 {qss_path}: {e}")

        QtCore.QTimer.singleShot(100, load_qss_async)  # 减少延迟时间


def setup_signal_handlers(tray_app):
    """设置信号处理器"""
    def signal_handler(signum, frame):
        print(f"\n收到信号 {signum}，正在安全退出...")
        QtCore.QTimer.singleShot(0, tray_app.quit)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def check_single_instance():
    """检查单实例运行"""
    from PySide6.QtNetwork import QLocalServer, QLocalSocket

    server_name = "AI_IDE_Auto_Run_Instance"
    socket = QLocalSocket()
    socket.connectToServer(server_name)

    if socket.waitForConnected(1000):
        print("应用已在运行中")
        return False

    # 创建本地服务器
    server = QLocalServer()
    server.listen(server_name)
    return True


def main():
    """主函数 - 重构版本"""
    # 性能计时器
    app_timer = QElapsedTimer()
    app_timer.start()

    # 注册清理函数
    import atexit
    def cleanup_on_exit():
        try:
            from capture import cleanup_global_cache_manager
            cleanup_global_cache_manager()
        except Exception as e:
            print(f"清理缓存管理器失败: {e}")

    atexit.register(cleanup_on_exit)

    # 创建应用
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("AI-IDE-Auto-Run")
    app.setApplicationVersion("4.0")
    app.setOrganizationName("AI-IDE-Tools")

    # 检查单实例
    if not check_single_instance():
        sys.exit(1)

    # 应用主题
    apply_modern_theme(app)

    # 检查系统托盘支持
    if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
        QtWidgets.QMessageBox.critical(None, "系统托盘", "系统不支持托盘功能")
        sys.exit(1)

    try:
        # 创建托盘应用
        tray_app = RefactoredTrayApp(app)

        # 设置信号处理器
        setup_signal_handlers(tray_app)

        # 显示托盘图标
        tray_app.show()

        # 记录启动完成时间
        startup_time = app_timer.elapsed()
        print(f"✅ 应用启动完成，总耗时: {startup_time}ms")

        # 测试模式：3秒后自动退出
        if os.environ.get('TEST_MODE') == '1':
            print("测试模式：3秒后自动退出...")
            QtCore.QTimer.singleShot(3000, tray_app.quit)

        # 启动事件循环
        if QASYNC_AVAILABLE and hasattr(tray_app, 'async_loop'):
            # 使用qasync事件循环
            import qasync
            with qasync.QEventLoop(app) as loop:
                loop.run_forever()
        else:
            # 使用标准Qt事件循环
            sys.exit(app.exec())

    except Exception as e:
        print(f"✗ 应用启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Windows平台multiprocessing保护
    if sys.platform.startswith('win'):
        import multiprocessing
        multiprocessing.freeze_support()

    main()

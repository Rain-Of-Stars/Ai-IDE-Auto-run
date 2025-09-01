# -*- coding: utf-8 -*-
"""
自动同意小工具 - 主入口：
- 托盘常驻后台运行，菜单包含：开始/停止扫描、设置、日志开关、退出。
- 采用 mss 截屏 + OpenCV 模板匹配；命中后通过 Windows 消息进行“无感点击”。
- 配置以 JSON 持久化，可在设置对话框中修改；日志可选写入 log.txt（带时间）。
"""
from __future__ import annotations
import os
import sys
import signal
import warnings

# 在导入Qt库之前关闭 qt.qpa.window 分类日志，以屏蔽
# “SetProcessDpiAwarenessContext() failed: 拒绝访问。” 的无害告警。
# 该告警通常因进程DPI感知已被其他组件设置导致，Qt再次设置返回E_ACCESSDENIED。
# 对功能无影响，但会在控制台输出中文提示，影响观感。
# 如需彻底避免Qt尝试设置DPI，可在创建QApplication前调用
# QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_DisableHighDpiScaling)
#（可能影响高DPI显示清晰度，默认不启用）。
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.window=false")

# 抑制 numpy 在导入时的实验性与数值精度相关告警，避免干扰控制台输出
# 注意：仅影响告警显示，不改变任何数值行为；需要彻底解决请改用发布构建的numpy
warnings.filterwarnings("ignore", message=r".*MINGW-W64.*", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning, module=r"numpy(\.|$)")
warnings.filterwarnings("ignore", category=UserWarning, module=r"numpy(\.|$)")

from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from typing import TYPE_CHECKING  # 仅用于类型检查的惰性导入

from auto_approve.config_manager import load_config, save_config, AppConfig
from auto_approve.logger_manager import enable_file_logging, get_logger
# 延迟导入扫描线程，避免应用启动即导入 numpy/cv2 产生控制台告警
# from scanner_worker import ScannerWorker
from auto_approve.settings_dialog import SettingsDialog

# 仅在类型检查时导入，避免运行期提前加载 numpy/cv2 等重依赖
if TYPE_CHECKING:
    from auto_approve.scanner_worker import ScannerWorker


# ---------- 外观主题 ----------

def apply_modern_theme(app: QtWidgets.QApplication):
    """应用现代化扁平主题与统一控件风格。
    优先加载本地QSS样式（modern_flat.qss），若不存在则回退Fusion暗色调。
    """
    # 统一字体（中文更友好）
    app.setFont(QtGui.QFont("Microsoft YaHei UI", 10))

    # 优先从工程化后的 assets/styles 目录加载
    qss_path = os.path.join(os.path.dirname(__file__), "assets", "styles", "modern_flat.qss")
    if os.path.exists(qss_path):
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
            return
        except Exception:
            pass

    # 回退：Fusion + 暗色调色板
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


# ---------- 托盘应用 ----------

class TrayApp(QtWidgets.QSystemTrayIcon):
    def __init__(self, app: QtWidgets.QApplication):
        # 使用自定义图标文件
        self.icon_path = os.path.join("assets", "icons", "icons", "custom_icon.ico")
        if os.path.exists(self.icon_path):
            icon = QtGui.QIcon(self.icon_path)
        else:
            # 如果图标文件不存在，使用备用的自定义绘制图标
            icon = self._create_custom_icon()
        super().__init__(icon)
        self.app = app
        self.setToolTip("AI-IDE-Auto-Run - 未启动")

        self.cfg: AppConfig = load_config()
        enable_file_logging(self.cfg.enable_logging)
        self.logger = get_logger()

        # 工作线程（延迟导入scanner_worker后创建）
        self.worker: "ScannerWorker" | None = None
        # 设置对话框单实例引用
        self.settings_dlg: SettingsDialog | None = None


        # 菜单
        self.menu = QtWidgets.QMenu()
        # 顶部三行状态：运行状态/后端/详细（屏幕轮询或匹配分）
        self.act_status = QtGui.QAction("状态: 未启动")
        self.act_status.setEnabled(False)
        self.act_backend = QtGui.QAction("后端: -")
        self.act_backend.setEnabled(False)
        self.act_detail = QtGui.QAction("")
        self.act_detail.setEnabled(False)

        self.act_start = QtGui.QAction("开始扫描")
        self.act_stop = QtGui.QAction("停止扫描")
        # 互斥勾选用于显示当前状态（白色✓）
        self._run_group = QtGui.QActionGroup(self.menu)
        self._run_group.setExclusive(True)
        self.act_start.setCheckable(True)
        self.act_stop.setCheckable(True)
        self._run_group.addAction(self.act_start)
        self._run_group.addAction(self.act_stop)
        # 默认未启动：勾选“停止扫描”
        self.act_stop.setChecked(True)
        # 连接行为
        self.act_start.triggered.connect(self.start_scanning)
        self.act_stop.triggered.connect(self.stop_scanning)

        self.menu.addAction(self.act_status)
        self.menu.addAction(self.act_backend)
        self.menu.addAction(self.act_detail)
        self.menu.addSeparator()
        self.menu.addAction(self.act_start)
        self.menu.addAction(self.act_stop)
        self.menu.addSeparator()

        self.act_logging = QtGui.QAction("启用日志到 log.txt")
        self.act_logging.setCheckable(True)
        self.act_logging.setChecked(self.cfg.enable_logging)
        self.act_logging.triggered.connect(self.toggle_logging)
        self.menu.addAction(self.act_logging)

        self.act_settings = QtGui.QAction("设置…")
        self.act_settings.triggered.connect(self.open_settings)
        self.menu.addAction(self.act_settings)
        


        self.menu.addSeparator()
        self.act_quit = QtGui.QAction("退出")
        self.act_quit.triggered.connect(self.quit)
        self.menu.addAction(self.act_quit)

        self.setContextMenu(self.menu)

        # 双击托盘图标：打开设置
        self.activated.connect(self._on_activated)

        # 为“无小图标”的系统通知准备一枚透明托盘图标
        # 说明：Windows 通知会在标题左侧显示触发托盘图标的小图标；
        # 通过使用透明图标的临时托盘来发送通知，可在视觉上去除该小图标。
        self._transparent_icon = self._create_transparent_icon(16)
        self._toast_tray = QtWidgets.QSystemTrayIcon(self._transparent_icon)
        self._toast_tray.setVisible(False)

        # 初始通知（尊重通知开关）
        self.show()
        self.notify_with_custom_icon("AI-IDE-Auto-Run", "已在后台托盘运行", self.icon_path, 3000)

        # 自动启动扫描
        if self.cfg.auto_start_scan:
            QtCore.QTimer.singleShot(500, self.start_scanning)

    def _create_custom_icon(self) -> QtGui.QIcon:
        """创建自定义颜色的托盘图标"""
        # 创建16x16像素的图标
        pixmap = QtGui.QPixmap(16, 16)
        pixmap.fill(QtGui.QColor("#D7E8D6"))  # 设置指定的绿色
        
        # 绘制一个简单的圆形图标
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # 设置画笔和画刷
        painter.setPen(QtGui.QPen(QtGui.QColor("#A8C8A7"), 1))  # 稍深的边框
        painter.setBrush(QtGui.QBrush(QtGui.QColor("#D7E8D6")))
        
        # 绘制圆形
        painter.drawEllipse(1, 1, 14, 14)
        
        # 绘制一个小的对勾符号
        painter.setPen(QtGui.QPen(QtGui.QColor("#4A7C59"), 2))  # 深绿色对勾
        painter.drawLine(4, 8, 7, 11)
        painter.drawLine(7, 11, 12, 5)
        
        painter.end()
        
        return QtGui.QIcon(pixmap)

    def _create_transparent_icon(self, size: int = 16) -> QtGui.QIcon:
        """创建完全透明的图标，用于隐藏通知标题左上角的小图标。"""
        pm = QtGui.QPixmap(size, size)
        pm.fill(QtCore.Qt.transparent)
        return QtGui.QIcon(pm)

    def _show_toast(self, title: str, message: str, icon_or_enum, msecs: int):
        """通过透明托盘发送系统通知，避免标题左上角的小图标显示。
        参数 icon_or_enum 可为 QIcon（显示为内容图片）或 QSystemTrayIcon.MessageIcon（信息级别）。
        """
        try:
            # 显示临时托盘以触发系统通知
            self._toast_tray.show()
            # 根据类型选择重载
            if isinstance(icon_or_enum, QtGui.QIcon):
                self._toast_tray.showMessage(title, message, icon_or_enum, msecs)
            else:
                self._toast_tray.showMessage(title, message, icon_or_enum, msecs)
        finally:
            # 稍后隐藏，避免托盘区域出现多余图标
            QtCore.QTimer.singleShot(100, self._toast_tray.hide)

    # ---------- 线程联动 ----------

    def _bind_worker_signals(self):
        assert self.worker is not None
        self.worker.sig_status.connect(self.on_status)
        self.worker.sig_hit.connect(self.on_hit)
        self.worker.sig_log.connect(self.on_log)

    def start_scanning(self):
        if self.worker is not None and self.worker.isRunning():
            return
        # 延迟导入，只有真正开始扫描时才加载依赖（numpy/cv2）
        from auto_approve.scanner_worker import ScannerWorker  # 延迟导入，降低启动开销

        self.cfg = load_config()  # 读取最新配置
        self.worker = ScannerWorker(self.cfg)
        self._bind_worker_signals()
        self.worker.start()

        # 菜单项始终可点；用✓表示当前状态
        self.act_start.setChecked(True)
        self.act_stop.setChecked(False)
        self.act_status.setText("状态: 运行中")
        # 启动时清空附加状态行
        self.act_backend.setText("后端: -")
        self.act_detail.setText("")
        self.setToolTip("AI-IDE-Auto-Run - 运行中")
        self.logger.info("扫描已启动")

    def stop_scanning(self):
        if self.worker is None:
            return
        self.worker.stop()
        self.worker.wait(3000)
        self.worker = None

        # 菜单项始终可点；用✓表示当前状态
        self.act_start.setChecked(False)
        self.act_stop.setChecked(True)
        self.act_status.setText("状态: 未启动")
        self.act_backend.setText("后端: -")
        self.act_detail.setText("")
        self.setToolTip("AI-IDE-Auto-Run - 未启动")
        self.logger.info("扫描已停止")

    # ---------- 托盘菜单逻辑 ----------
    def notify(self, title: str, message: str, icon: QtWidgets.QSystemTrayIcon.MessageIcon = QtWidgets.QSystemTrayIcon.Information, msecs: int = 2000):
        """托盘通知封装：根据配置决定是否显示通知。
        参数说明：
        - title/message: 通知标题与内容
        - icon: 通知图标类型
        - msecs: 显示毫秒数
        """
        try:
            # 读取最新配置以确保切换后立即生效
            self.cfg = load_config()
        except Exception:
            pass
        if getattr(self.cfg, "enable_notifications", True):
            # 使用透明托盘发送以隐藏标题左上角的小图标
            try:
                self._show_toast(title, message, QtWidgets.QSystemTrayIcon.NoIcon, msecs)
            except Exception:
                # 兜底：直接使用当前托盘
                self.showMessage(title, message, icon, msecs)
    
    def notify_with_custom_icon(self, title: str, message: str, custom_icon_path: str = None, msecs: int = 2000):
        """托盘通知封装：使用自定义图标显示通知。
        参数说明：
        - title/message: 通知标题与内容
        - custom_icon_path: 自定义图标文件路径，如果为None则使用托盘图标
        - msecs: 显示毫秒数
        """
        try:
            # 读取最新配置以确保切换后立即生效
            self.cfg = load_config()
        except Exception:
            pass
        if getattr(self.cfg, "enable_notifications", True):
            # 使用自定义图标显示通知（并通过透明托盘隐藏标题的小图标）
            custom_icon = None
            try:
                if custom_icon_path and isinstance(custom_icon_path, (str, bytes)) and os.path.exists(custom_icon_path):
                    custom_icon = QtGui.QIcon(custom_icon_path)
                else:
                    custom_icon = QtGui.QIcon()  # 空图标：不显示内容图
                self._show_toast(title, message, custom_icon, msecs)
            except Exception:
                # 兜底：直接使用当前托盘
                if isinstance(custom_icon, QtGui.QIcon) and not custom_icon.isNull():
                    self.showMessage(title, message, custom_icon, msecs)
                else:
                    self.showMessage(title, message, QtWidgets.QSystemTrayIcon.NoIcon, msecs)

    def toggle_logging(self, checked: bool):
        self.cfg = load_config()
        self.cfg.enable_logging = bool(checked)
        save_config(self.cfg)
        enable_file_logging(self.cfg.enable_logging)
        self.notify_with_custom_icon("日志设置", "文件日志已{}".format("开启" if checked else "关闭"), self.icon_path, 2000)

    def open_settings(self):
        """打开设置窗口：若已存在则仅聚焦置前，不重复创建。
        说明：不再依赖 isVisible() 判断，避免快速连续触发时（窗口尚未来得及显示）
        出现竞态导致重复创建多个设置窗口。
        """
        # 若已有窗口（无论当前是否已显示），则只做聚焦与置前
        if self.settings_dlg is not None:
            self._focus_window(self.settings_dlg)
            return

        # 创建新窗口并保持引用，防止重复实例
        self.settings_dlg = SettingsDialog()
        # 关闭时自动销毁对象，避免悬挂引用
        self.settings_dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        # 连接信号：保存后更新配置；无论结果如何，结束时清理引用
        self.settings_dlg.accepted.connect(self._on_settings_accepted)
        # 新增：监听“saved”信号（保存但不关闭窗口）
        try:
            self.settings_dlg.saved.connect(self._on_settings_accepted)
        except Exception:
            pass
        self.settings_dlg.finished.connect(self._on_settings_finished)
        # 显示并置前（使用非阻塞show，保证托盘可响应后续点击）
        self.settings_dlg.show()
        self._focus_window(self.settings_dlg)

    def _on_settings_accepted(self, *_args):
        """设置窗口点击保存后回调：重新加载并应用配置。
        说明：兼容 SettingsDialog.saved(cfg: AppConfig) 信号携带的参数，
        避免因参数不匹配导致回调未触发。
        """
        # 记录保存前关键字段，用于判断是否需要重启扫描线程
        prev_cfg = getattr(self, "cfg", None)
        prev_backend = getattr(prev_cfg, "capture_backend", "screen") if prev_cfg else "screen"
        was_running = bool(self.worker is not None and self.worker.isRunning())

        # 读取最新配置并应用通用开关
        self.cfg = load_config()
        enable_file_logging(self.cfg.enable_logging)
        
        # 同步托盘菜单状态：确保右键菜单与UI设置保持一致
        self._sync_tray_menu_state()

        # 若线程在运行：
        # - 当捕获后端发生变化（如 从"传统屏幕"切到"窗口级/自动"或相反），
        #   需要重启线程以重新初始化具体后端与相关资源；
        # - 其他参数变化仍走无中断的 update_config。
        if was_running:
            new_backend = getattr(self.cfg, "capture_backend", "screen")
            if str(new_backend).lower() != str(prev_backend).lower():
                # 先停止再延时启动，避免阻塞UI
                self.stop_scanning()
                QtCore.QTimer.singleShot(200, self.start_scanning)
            else:
                # 后端未变化，动态更新即可
                self.worker.update_config(self.cfg)

        # 立即反馈
        self.notify_with_custom_icon("设置", "配置已保存", self.icon_path, 2000)

    def _on_settings_finished(self, _result: int):
        """设置窗口关闭后回调：清理单实例引用。"""
        self.settings_dlg = None

    def _sync_tray_menu_state(self):
        """同步托盘菜单状态：确保右键菜单与UI设置保持一致。"""
        # 同步日志开关状态
        self.act_logging.setChecked(self.cfg.enable_logging)

    def _focus_window(self, w: QtWidgets.QWidget):
        """将窗口置于前台并获取焦点（尽量兼容Windows前台限制）。"""
        try:
            # 先确保可见
            if w.isMinimized():
                w.showNormal()
            else:
                w.show()
            # 再尝试提升与激活
            w.raise_()
            w.activateWindow()
            # 部分系统上需要异步再激活一次以确保前置
            QtCore.QTimer.singleShot(0, w.activateWindow)
        except Exception:
            # 兜底：即便失败也不影响功能
            pass
    


    def quit(self):
        self.stop_scanning()
        self.hide()
        QtCore.QCoreApplication.quit()

    # ---------- 信号响应 ----------

    def on_status(self, text: str):
        """更新托盘菜单的状态行。
        规则：
        - 第一行：仅显示运行状态（原样或去掉后续分段）
        - 第二行：后端信息（若存在“后端:”片段），否则为“后端: -”
        - 第三行：详细信息
          • 多屏轮询：还原为“当前屏幕: N | 匹配: S”
          • 否则：使用“上次匹配: S”
        """
        raw = text or ""
        parts = [p.strip() for p in raw.split('|')]

        # 行1：状态
        line1 = parts[0] if parts else raw
        self.act_status.setText(f"状态: {line1}")

        # 行2：后端
        backend = "-"
        for p in parts:
            if p.startswith("后端:"):
                backend = p.split("后端:", 1)[1].strip()
                break
        self.act_backend.setText(f"后端: {backend}")

        # 行3：详细
        detail = ""
        # 优先还原多屏轮询提示
        has_multi = any("多屏轮询" in p for p in parts)
        cur_screen = None
        score_text = None
        for p in parts:
            if p.startswith("当前屏幕:"):
                cur_screen = p
            if p.startswith("匹配:") or p.startswith("上次匹配:"):
                # 统一提取分数部分
                score_text = p.replace("上次匹配:", "匹配:").strip()
        if has_multi and (cur_screen or score_text):
            detail = " | ".join(filter(None, [cur_screen, score_text]))
        else:
            # 非多屏：回退为“上次匹配”或“匹配”片段
            for p in parts[::-1]:
                if p.startswith("上次匹配:") or p.startswith("匹配:"):
                    detail = p
                    break
        self.act_detail.setText(detail)

        # Tooltip 使用多行展示
        tooltip = "AI-IDE-Auto-Run - " + "\n".join(filter(None, [self.act_status.text(), self.act_backend.text(), self.act_detail.text()]))
        self.setToolTip(tooltip)

    def on_hit(self, score: float, sx: int, sy: int):
        self.notify_with_custom_icon("已自动点击", f"score={score:.3f} @ ({sx},{sy})", self.icon_path, 2500)

    def on_log(self, text: str):
        # 仅提示关键日志，避免频繁打扰
        self.logger.info(text)

    def _on_activated(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason):
        if reason == QtWidgets.QSystemTrayIcon.DoubleClick:
            self.open_settings()


# ---------- 入口 ----------

def main():
    # Windows 下确保 Ctrl+C 可退出（在控制台运行时）
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # 设置应用程序名称和显示名称（用于通知消息标题）
    app.setApplicationName("AI-IDE-Auto-Run")
    app.setApplicationDisplayName("AI-IDE-Auto-Run")
    
    # 设置应用程序图标（用于通知消息）
    icon_path = os.path.join("assets", "icons", "icons", "custom_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QtGui.QIcon(icon_path))
    
    apply_modern_theme(app)

    # ========== 进程级单实例：QLocalServer/QLocalSocket ==========
    # 若已存在实例：发送聚焦设置窗口请求并退出当前进程
    instance_name = "auto_approve_tray_singleton"
    sock = QLocalSocket()
    sock.connectToServer(instance_name)
    if sock.waitForConnected(150):
        try:
            sock.write(b"show_settings")
            sock.flush()
            sock.waitForBytesWritten(150)
        finally:
            sock.disconnectFromServer()
        # 直接退出，不再创建第二个托盘实例
        return

    # 可能存在上次崩溃留下的同名服务器，先尝试清理
    try:
        QLocalServer.removeServer(instance_name)
    except Exception:
        pass

    # 启动本实例的本地服务器，接收来自后续启动实例的“聚焦设置”请求
    server = QLocalServer()
    server.listen(instance_name)

    tray = TrayApp(app)

    def _handle_incoming():
        # 处理新连接，读取命令并触发前台聚焦
        client = server.nextPendingConnection()
        if client is None:
            return
        def _read_and_handle():
            try:
                data = bytes(client.readAll()).decode("utf-8", errors="ignore").strip()
                cmd = data or "show_settings"
                # 统一处理为打开/聚焦设置窗口
                tray.open_settings()
            finally:
                try:
                    client.disconnectFromServer()
                except Exception:
                    pass
                client.close()
        # 有的系统连接建立即带数据；保险起见立即与异步各触发一次
        _read_and_handle()
        QtCore.QTimer.singleShot(0, _read_and_handle)

    server.newConnection.connect(_handle_incoming)
    # 保持引用，避免被GC
    tray._single_instance_server = server  # noqa: SLF001

    # 阻塞到事件循环结束
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

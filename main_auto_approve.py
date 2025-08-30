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

# 在导入Qt库之前关闭 qt.qpa.window 分类日志，以屏蔽
# “SetProcessDpiAwarenessContext() failed: 拒绝访问。” 的无害告警。
# 该告警通常因进程DPI感知已被其他组件设置导致，Qt再次设置返回E_ACCESSDENIED。
# 对功能无影响，但会在控制台输出中文提示，影响观感。
# 如需彻底避免Qt尝试设置DPI，可在创建QApplication前调用
# QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_DisableHighDpiScaling)
#（可能影响高DPI显示清晰度，默认不启用）。
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.window=false")

from PySide6 import QtWidgets, QtGui, QtCore

from config_manager import load_config, save_config, AppConfig
from logger_manager import enable_file_logging, get_logger
from scanner_worker import ScannerWorker
from settings_dialog import SettingsDialog
from screen_list_dialog import show_screen_list_dialog


# ---------- 外观主题 ----------

def apply_modern_theme(app: QtWidgets.QApplication):
    """应用现代化扁平主题与统一控件风格。
    优先加载本地QSS样式（modern_flat.qss），若不存在则回退Fusion暗色调。
    """
    # 统一字体（中文更友好）
    app.setFont(QtGui.QFont("Microsoft YaHei UI", 10))

    qss_path = os.path.join(os.path.dirname(__file__), "modern_flat.qss")
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
        # 创建自定义绿色图标
        icon = self._create_custom_icon()
        super().__init__(icon)
        self.app = app
        self.setToolTip("自动同意 - 未启动")

        self.cfg: AppConfig = load_config()
        enable_file_logging(self.cfg.enable_logging)
        self.logger = get_logger()

        # 工作线程
        self.worker: ScannerWorker | None = None

        # 菜单
        self.menu = QtWidgets.QMenu()
        self.act_status = QtGui.QAction("状态: 未启动")
        self.act_status.setEnabled(False)

        self.act_start = QtGui.QAction("开始扫描")
        self.act_start.triggered.connect(self.start_scanning)

        self.act_stop = QtGui.QAction("停止扫描")
        self.act_stop.setEnabled(False)
        self.act_stop.triggered.connect(self.stop_scanning)

        self.menu.addAction(self.act_status)
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
        
        self.act_screen_list = QtGui.QAction("显示屏幕列表")
        self.act_screen_list.triggered.connect(self.show_screen_list)
        self.menu.addAction(self.act_screen_list)

        self.menu.addSeparator()
        self.act_quit = QtGui.QAction("退出")
        self.act_quit.triggered.connect(self.quit)
        self.menu.addAction(self.act_quit)

        self.setContextMenu(self.menu)

        # 双击托盘图标：打开设置
        self.activated.connect(self._on_activated)

        # 初始通知
        self.show()
        self.showMessage("自动同意", "已在后台托盘运行", QtWidgets.QSystemTrayIcon.Information, 3000)

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

    # ---------- 线程联动 ----------

    def _bind_worker_signals(self):
        assert self.worker is not None
        self.worker.sig_status.connect(self.on_status)
        self.worker.sig_hit.connect(self.on_hit)
        self.worker.sig_log.connect(self.on_log)

    def start_scanning(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self.cfg = load_config()  # 读取最新配置
        self.worker = ScannerWorker(self.cfg)
        self._bind_worker_signals()
        self.worker.start()

        self.act_start.setEnabled(False)
        self.act_stop.setEnabled(True)
        self.act_status.setText("状态: 运行中")
        self.setToolTip("自动同意 - 运行中")
        self.logger.info("扫描已启动")

    def stop_scanning(self):
        if self.worker is None:
            return
        self.worker.stop()
        self.worker.wait(3000)
        self.worker = None

        self.act_start.setEnabled(True)
        self.act_stop.setEnabled(False)
        self.act_status.setText("状态: 未启动")
        self.setToolTip("自动同意 - 未启动")
        self.logger.info("扫描已停止")

    # ---------- 托盘菜单逻辑 ----------

    def toggle_logging(self, checked: bool):
        self.cfg = load_config()
        self.cfg.enable_logging = bool(checked)
        save_config(self.cfg)
        enable_file_logging(self.cfg.enable_logging)
        self.showMessage("日志设置", "文件日志已{}".format("开启" if checked else "关闭"),
                         QtWidgets.QSystemTrayIcon.Information, 2000)

    def open_settings(self):
        dlg = SettingsDialog()
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            # 用户保存了配置
            self.cfg = load_config()
            enable_file_logging(self.cfg.enable_logging)
            # 运行中则应用新配置
            if self.worker is not None and self.worker.isRunning():
                self.worker.update_config(self.cfg)
            self.showMessage("设置", "配置已保存", QtWidgets.QSystemTrayIcon.Information, 2000)
    
    def show_screen_list(self):
        """显示屏幕列表对话框"""
        try:
            selected_screen = show_screen_list_dialog()
            self.logger.info(f"用户查看了屏幕列表，当前选择屏幕: {selected_screen}")
        except Exception as e:
            self.logger.error(f"显示屏幕列表时发生错误: {e}")
            QtWidgets.QMessageBox.warning(
                None, "错误", 
                f"显示屏幕列表时发生错误：\n{str(e)}"
            )

    def quit(self):
        self.stop_scanning()
        self.hide()
        QtCore.QCoreApplication.quit()

    # ---------- 信号响应 ----------

    def on_status(self, text: str):
        self.act_status.setText(f"状态: {text}")
        self.setToolTip(f"自动同意 - {text}")

    def on_hit(self, score: float, sx: int, sy: int):
        self.showMessage("已自动点击", f"score={score:.3f} @ ({sx},{sy})",
                         QtWidgets.QSystemTrayIcon.Information, 2500)

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
    apply_modern_theme(app)

    tray = TrayApp(app)

    # 阻塞到事件循环结束
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

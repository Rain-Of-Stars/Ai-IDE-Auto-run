# -*- coding: utf-8 -*-
"""
HWND 获取工具（集成到设置中使用）：
- 列出可见窗口并搜索过滤；
- 支持拖拽十字准星到目标窗口获取 HWND；
- 显示窗口详细信息；
- 支持“测试捕获”调用窗口级截屏后端验证。
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
from typing import Optional, Tuple

from PySide6 import QtWidgets, QtCore, QtGui

from auto_approve.wgc_capture import find_window_by_title, is_electron_process, WindowCaptureManager


# Windows API
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)

user32.GetCursorPos.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(ctypes.wintypes.POINT)]

user32.WindowFromPoint.restype = wintypes.HWND
user32.WindowFromPoint.argtypes = [ctypes.wintypes.POINT]

user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]

user32.GetClassNameW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]

user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]

user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]

psapi.GetModuleFileNameExW.restype = wintypes.DWORD
psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]

kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


class WindowInfo:
    """窗口信息封装。"""
    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self.title = self._get_window_title()
        self.class_name = self._get_class_name()
        self.rect = self._get_window_rect()
        self.process_name = self._get_process_name()
        self.process_id = self._get_process_id()
        self.is_electron = is_electron_process(hwnd)
        self.is_visible = bool(user32.IsWindowVisible(hwnd))

    def _get_window_title(self) -> str:
        try:
            length = user32.GetWindowTextLengthW(self.hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(self.hwnd, buf, length + 1)
                return buf.value
        except Exception:
            pass
        return ""

    def _get_class_name(self) -> str:
        try:
            buf = ctypes.create_unicode_buffer(256)
            n = user32.GetClassNameW(self.hwnd, buf, 256)
            if n > 0:
                return buf.value
        except Exception:
            pass
        return ""

    def _get_window_rect(self):
        try:
            rect = wintypes.RECT()
            if user32.GetWindowRect(self.hwnd, ctypes.byref(rect)):
                return {
                    'left': rect.left,
                    'top': rect.top,
                    'right': rect.right,
                    'bottom': rect.bottom,
                    'width': rect.right - rect.left,
                    'height': rect.bottom - rect.top,
                }
        except Exception:
            pass
        return None

    def _get_process_id(self) -> int:
        try:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(self.hwnd, ctypes.byref(pid))
            return pid.value
        except Exception:
            return 0

    def _get_process_name(self) -> str:
        try:
            pid = self._get_process_id()
            if not pid:
                return ""
            h = kernel32.OpenProcess(0x0400, False, pid)
            if not h:
                return ""
            try:
                buf = ctypes.create_unicode_buffer(260)
                if psapi.GetModuleFileNameExW(h, None, buf, 260):
                    return buf.value
            finally:
                kernel32.CloseHandle(h)
        except Exception:
            pass
        return ""


class WindowListWidget(QtWidgets.QTableWidget):
    """窗口列表控件。"""
    window_selected = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(0, 3, parent)
        self.setHorizontalHeaderLabels(["HWND", "标题", "进程"])
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.itemSelectionChanged.connect(self._on_sel)
        self.refresh_window_list()

    def refresh_window_list(self):
        """枚举可见窗口并填充表格。"""
        self.setRowCount(0)

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_proc(hwnd, _lp):
            if not user32.IsWindowVisible(hwnd):
                return True
            ln = user32.GetWindowTextLengthW(hwnd)
            if ln <= 0:
                return True
            buf = ctypes.create_unicode_buffer(ln + 1)
            user32.GetWindowTextW(hwnd, buf, ln + 1)
            title = buf.value
            info = WindowInfo(hwnd)
            row = self.rowCount()
            self.insertRow(row)
            self.setItem(row, 0, QtWidgets.QTableWidgetItem(str(hwnd)))
            self.setItem(row, 1, QtWidgets.QTableWidgetItem(title))
            self.setItem(row, 2, QtWidgets.QTableWidgetItem(info.process_name))
            return True

        user32.EnumWindows(enum_proc, 0)
        self.resizeColumnsToContents()

    def _on_sel(self):
        rows = self.selectionModel().selectedRows()
        if rows:
            hwnd = int(self.item(rows[0].row(), 0).text())
            self.window_selected.emit(hwnd)


class CrosshairWidget(QtWidgets.QWidget):
    """十字准星：按下左键后拖拽到目标窗口释放即可选中。"""
    window_picked = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.setCursor(QtCore.Qt.CrossCursor)
        self._dragging = False
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._update_target)
        self._cur_hwnd = 0

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setBrush(QtGui.QBrush(QtGui.QColor(47, 128, 237)))
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2))
        p.drawEllipse(2, 2, 28, 28)
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 3))
        p.drawLine(16, 6, 16, 26)
        p.drawLine(6, 16, 26, 16)

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._dragging = True
            self._timer.start(50)
            self.grabMouse()

    def mouseReleaseEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton and self._dragging:
            self._dragging = False
            self._timer.stop()
            self.releaseMouse()
            if self._cur_hwnd:
                self.window_picked.emit(self._cur_hwnd)

    def _update_target(self):
        if not self._dragging:
            return
        pt = wintypes.POINT()
        if user32.GetCursorPos(ctypes.byref(pt)):
            hwnd = user32.WindowFromPoint(pt)
            if hwnd and hwnd != self._cur_hwnd:
                self._cur_hwnd = hwnd
                try:
                    info = WindowInfo(hwnd)
                    self.setToolTip(f"HWND: {hwnd}\n标题: {info.title}\n进程: {info.process_name}")
                except Exception:
                    self.setToolTip(f"HWND: {hwnd}")


class HWNDPickerDialog(QtWidgets.QDialog):
    """HWND 获取对话框。"""
    hwnd_selected = QtCore.Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HWND获取工具")
        self.resize(820, 600)
        self._sel_hwnd = 0
        self._sel_title = ""
        self._init_ui()
        self._connect()
        self.list.refresh_window_list()

    def _init_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel("选择目标窗口以获取HWND")
        title.setStyleSheet("font-weight: bold; color: #4A9EFF;")
        v.addWidget(title)

        # 工具条
        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(QtWidgets.QLabel("搜索:"))
        self.ed_search = QtWidgets.QLineEdit()
        self.ed_search.setPlaceholderText("输入窗口标题关键词…")
        bar.addWidget(self.ed_search, 1)
        self.btn_refresh = QtWidgets.QPushButton("刷新列表")
        self.btn_refresh.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        bar.addWidget(self.btn_refresh)
        bar.addWidget(QtWidgets.QLabel("拖拽选择:"))
        self.cross = CrosshairWidget()
        bar.addWidget(self.cross)
        bar.addStretch(1)
        v.addLayout(bar)

        # 窗口列表
        self.list = WindowListWidget()
        v.addWidget(self.list, 1)

        # 详细信息
        grp = QtWidgets.QGroupBox("选中窗口信息")
        form = QtWidgets.QFormLayout(grp)
        self.info_hwnd = QtWidgets.QLineEdit(); self.info_hwnd.setReadOnly(True)
        self.info_title = QtWidgets.QLineEdit(); self.info_title.setReadOnly(True)
        self.info_class = QtWidgets.QLineEdit(); self.info_class.setReadOnly(True)
        self.info_proc = QtWidgets.QLineEdit(); self.info_proc.setReadOnly(True)
        self.info_size = QtWidgets.QLineEdit(); self.info_size.setReadOnly(True)
        self.chk_ele = QtWidgets.QCheckBox("Electron进程"); self.chk_ele.setEnabled(False)
        form.addRow("HWND:", self.info_hwnd)
        form.addRow("标题:", self.info_title)
        form.addRow("类名:", self.info_class)
        form.addRow("进程:", self.info_proc)
        form.addRow("尺寸:", self.info_size)
        form.addRow("", self.chk_ele)
        v.addWidget(grp)

        # 按钮区
        h = QtWidgets.QHBoxLayout()
        self.btn_test = QtWidgets.QPushButton("测试捕获")
        self.btn_ok = QtWidgets.QPushButton("确定"); self.btn_ok.setObjectName("primary"); self.btn_ok.setEnabled(False)
        self.btn_cancel = QtWidgets.QPushButton("取消")
        h.addWidget(self.btn_test)
        h.addStretch(1)
        h.addWidget(self.btn_ok)
        h.addWidget(self.btn_cancel)
        v.addLayout(h)

    def _connect(self):
        self.btn_refresh.clicked.connect(self.list.refresh_window_list)
        self.ed_search.textChanged.connect(self._on_search)
        self.cross.window_picked.connect(self._on_pick)
        self.list.window_selected.connect(self._on_select)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_test.clicked.connect(self._on_test)

    def _on_search(self, text: str):
        for r in range(self.list.rowCount()):
            item = self.list.item(r, 1)
            ok = (text.lower() in item.text().lower()) if text else True
            self.list.setRowHidden(r, not ok)

    def _on_pick(self, hwnd: int):
        self._select(hwnd)

    def _on_select(self, hwnd: int):
        self._select(hwnd)

    def _select(self, hwnd: int):
        try:
            info = WindowInfo(hwnd)
            self._sel_hwnd = hwnd
            self._sel_title = info.title
            self.info_hwnd.setText(str(hwnd))
            self.info_title.setText(info.title)
            self.info_class.setText(info.class_name)
            self.info_proc.setText(info.process_name)
            if info.rect:
                self.info_size.setText(f"{info.rect['width']} × {info.rect['height']}")
            else:
                self.info_size.setText("未知")
            self.chk_ele.setChecked(info.is_electron)
            self.btn_ok.setEnabled(True)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "错误", f"获取窗口信息失败: {e}")

    def _on_test(self):
        if not self._sel_hwnd:
            QtWidgets.QMessageBox.warning(self, "提示", "请先选择窗口")
            return
        try:
            cap = WindowCaptureManager(self._sel_hwnd, fps_max=10, timeout_ms=3000, restore_minimized=True)
            img = cap.capture_frame()
            cap.cleanup()
            if img is None:
                QtWidgets.QMessageBox.warning(self, "测试失败", "窗口捕获失败，可能窗口不可见/已关闭/不支持")
                return
            # 显示预览
            import cv2, time
            h, w = img.shape[:2]
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            qimg = QtGui.QImage(rgb.data, w, h, rgb.strides[0], QtGui.QImage.Format_RGB888)
            pm = QtGui.QPixmap.fromImage(qimg)
            from auto_approve.settings_dialog import ScreenshotPreviewDialog
            dlg = ScreenshotPreviewDialog(pm, self)
            dlg.setWindowTitle("WGC捕获测试")
            if dlg.exec() == QtWidgets.QDialog.Accepted:
                path = f"wgc_test_capture_{int(time.time())}.png"
                cv2.imwrite(path, img)
                QtWidgets.QMessageBox.information(self, "已保存", f"图片保存到: {path}")
            else:
                QtWidgets.QMessageBox.information(self, "成功", f"捕获成功，尺寸: {w}×{h}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"测试捕获出错: {e}")

    def get_selected_hwnd(self) -> Tuple[int, str]:
        return self._sel_hwnd, self._sel_title


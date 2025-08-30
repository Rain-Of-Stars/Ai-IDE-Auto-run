# -*- coding: utf-8 -*-
"""
设置对话框：允许用户配置模板路径、阈值、扫描间隔、ROI、显示器索引、冷却时间、
灰度/多尺度/缩放倍率、点击偏移、最少命中帧、启动即扫描与日志开关，并保存到 JSON。
"""
from __future__ import annotations
import os
from typing import Tuple, List

from PySide6 import QtWidgets, QtCore, QtGui

from auto_approve.config_manager import AppConfig, ROI, save_config, load_config


class CustomCheckBox(QtWidgets.QCheckBox):
    """自定义复选框，使用代码绘制白色✓符号，不依赖图标资源文件。"""
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        
    def paintEvent(self, event):
        """重写绘制事件，自定义绘制选中状态的白色✓符号。"""
        # 先调用父类的绘制方法绘制基础样式
        super().paintEvent(event)
        
        # 如果选中状态，绘制白色✓符号
        if self.isChecked():
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            
            # 获取指示器的矩形区域
            option = QtWidgets.QStyleOptionButton()
            self.initStyleOption(option)
            indicator_rect = self.style().subElementRect(
                QtWidgets.QStyle.SE_CheckBoxIndicator, option, self
            )
            
            # 设置白色画笔绘制✓符号
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
            
            # 计算✓符号的坐标
            center_x = indicator_rect.center().x()
            center_y = indicator_rect.center().y()
            size = min(indicator_rect.width(), indicator_rect.height()) * 0.6
            
            # 绘制✓符号的两条线段
            # 第一条线段：从左下到中心
            x1 = center_x - size * 0.3
            y1 = center_y + size * 0.1
            x2 = center_x - size * 0.1
            y2 = center_y + size * 0.3
            painter.drawLine(QtCore.QPointF(x1, y1), QtCore.QPointF(x2, y2))
            
            # 第二条线段：从中心到右上
            x3 = center_x + size * 0.4
            y3 = center_y - size * 0.2
            painter.drawLine(QtCore.QPointF(x2, y2), QtCore.QPointF(x3, y3))
            
            painter.end()

class ImagePreviewDialog(QtWidgets.QDialog):
    """简单的图片预览对话框，随窗口大小自适应缩放。"""
    def __init__(self, pixmap: QtGui.QPixmap, path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"预览 - {os.path.basename(path)}")
        self.resize(720, 540)
        self._pixmap = pixmap
        self._label = QtWidgets.QLabel()
        self._label.setAlignment(QtCore.Qt.AlignCenter)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.addWidget(self._label, 1)
        self._update_view()

    def resizeEvent(self, e: QtGui.QResizeEvent) -> None:
        super().resizeEvent(e)
        self._update_view()

    def _update_view(self):
        if self._pixmap.isNull():
            self._label.setText("无法加载图片")
            return
        scaled = self._pixmap.scaled(self._label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self._label.setPixmap(scaled)

class ScreenshotPreviewDialog(QtWidgets.QDialog):
    """截图确认预览对话框：显示图片，并提供保存/取消按钮。

    设计要点：
    - 仅负责展示与返回用户意图，不直接负责文件保存；
    - 保存按钮对象名设为primary，匹配现有QSS主按钮样式；
    - 预览区自适应窗口尺寸，平滑缩放。
    """
    def __init__(self, pixmap: QtGui.QPixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("截图预览")
        self.resize(820, 580)
        self._pixmap = pixmap

        # 预览标签
        self._label = QtWidgets.QLabel()
        self._label.setAlignment(QtCore.Qt.AlignCenter)

        # 底部按钮：保存/取消（保存置于首位并标记为主按钮）
        self.btn_save = QtWidgets.QPushButton("保存")
        self.btn_save.setObjectName("primary")  # 使用样式表中的主按钮配色
        self.btn_cancel = QtWidgets.QPushButton("取消")
        self.btn_save.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        # 布局
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.addWidget(self._label, 1)
        h = QtWidgets.QHBoxLayout()
        h.addStretch(1)
        h.addWidget(self.btn_save)
        h.addWidget(self.btn_cancel)
        v.addLayout(h)

        self._update_view()

    def resizeEvent(self, e: QtGui.QResizeEvent) -> None:
        super().resizeEvent(e)
        self._update_view()

    def _update_view(self):
        """更新预览图显示，按保持比例缩放到标签尺寸。"""
        if self._pixmap.isNull():
            self._label.setText("无法加载图片")
            return
        scaled = self._pixmap.scaled(self._label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self._label.setPixmap(scaled)

class RegionSnipDialog(QtWidgets.QDialog):
    """全屏截图取框对话框：左键拖拽选择；右键或Esc取消。

    关键增强：
    - 跟随鼠标所在屏幕：在未拖拽时，鼠标移到哪个屏幕，取框覆盖就切到哪个屏幕；
    - 高DPI安全：按截图像素比进行区域拷贝，避免缩放误差。
    """
    def __init__(self, screen: QtGui.QScreen, background: QtGui.QPixmap, parent=None):
        super().__init__(parent)
        # 使用无边框置顶窗口，但不启用窗口级半透明。
        # 说明：跨屏（不同DPI）移动时，WA_TranslucentBackground 在 Windows 上偶发出现
        # 叠加缓冲未刷新导致的灰色残影/透明异常。由于我们自己绘制了全屏截图和半透明遮罩，
        # 并不需要窗口级透明，因此显式关闭以规避问题。
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog | QtCore.Qt.WindowStaysOnTopHint)
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, False)
        # 对话框关闭后立即销毁，避免定时器等异步回调导致重新显示
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self._screen = screen  # 当前覆盖的屏幕
        self._bg = background  # 当前屏幕截图
        # 显式同步截图的DPR，避免跨屏切换时出现缩放错位
        try:
            self._bg.setDevicePixelRatio(self._screen.devicePixelRatio())
        except Exception:
            pass
        self._origin = None
        self._current = None
        self.selected_pixmap: QtGui.QPixmap | None = None
        # 关闭标志：accept/reject后置为True，所有异步流程应尽快退出
        self._closing: bool = False
        # 绑定到当前屏幕并匹配几何
        self._apply_screen(screen)
        self.setGeometry(screen.geometry())
        self._hint_font = self.font()
        self._hint_font.setPointSize(self._hint_font.pointSize() + 1)

        # 拖拽标志：按下左键开始，释放后结束
        self._dragging: bool = False

        # 鼠标屏幕跟随定时器：未拖拽时根据鼠标位置切换覆盖屏幕
        self._cursor_timer = QtCore.QTimer(self)
        self._cursor_timer.setInterval(80)  # 80ms足够流畅
        self._cursor_timer.timeout.connect(self._follow_cursor_screen)
        self._cursor_timer.start()

    # ---------- 生命周期与关闭控制 ----------
    def _shutdown_timer(self):
        """安全停止内部定时器（多次调用无副作用）。"""
        try:
            if hasattr(self, "_cursor_timer") and self._cursor_timer is not None:
                self._cursor_timer.stop()
                try:
                    self._cursor_timer.timeout.disconnect(self._follow_cursor_screen)
                except Exception:
                    pass
        except Exception:
            pass

    def accept(self) -> None:
        """确认选择：停止定时器并隐藏窗口，避免覆盖层残留。"""
        self._dragging = False
        self._closing = True
        self._shutdown_timer()
        # 先隐藏，防止定时器尾调用触发 _switch_to_screen 把窗口又显示出来
        try:
            # 降级去顶置，避免极端情况下的置顶残留
            self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, False)
            self.setWindowOpacity(0.0)
            self.show()  # 应用窗口标志变更
            self.hide()
        except Exception:
            pass
        # 立即刷新事件队列，尽快让系统移除窗口
        try:
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
        except Exception:
            pass
        super().accept()

    def reject(self) -> None:
        """取消：同样停止定时器并隐藏窗口。"""
        self._dragging = False
        self._closing = True
        self._shutdown_timer()
        try:
            self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, False)
            self.setWindowOpacity(0.0)
            self.show()
            self.hide()
        except Exception:
            pass
        try:
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
        except Exception:
            pass
        super().reject()

    def closeEvent(self, e: QtGui.QCloseEvent) -> None:
        """关闭事件：兜底停止定时器。"""
        self._closing = True
        self._shutdown_timer()
        super().closeEvent(e)

    def _apply_screen(self, screen: QtGui.QScreen):
        """将窗口绑定到指定屏幕（用于跨屏与DPI调整）。"""
        try:
            handle = self.windowHandle()
            if handle is not None and screen is not None:
                handle.setScreen(screen)
        except Exception:
            pass

    def _switch_to_screen(self, screen: QtGui.QScreen):
        """切换覆盖到指定屏幕：更新窗口几何与背景截图，并重置选择状态。"""
        # 若窗口已不可见（例如刚刚 accept/reject 关闭），避免被再次显示
        if self._closing or not self.isVisible():
            return
        if screen is None or screen is self._screen:
            return
        self._screen = screen
        try:
            self._bg = self._screen.grabWindow(0)
            try:
                self._bg.setDevicePixelRatio(self._screen.devicePixelRatio())
            except Exception:
                pass
        except Exception:
            # 若截屏失败则保持原图，避免崩溃
            pass
        # 切换屏幕后重置选择，避免坐标空间混淆
        self._origin = None
        self._current = None
        self._apply_screen(self._screen)
        self.setGeometry(self._screen.geometry())
        # 仅在可见状态下刷新前置，避免在关闭过程中被重新显示
        if not self._closing and self.isVisible():
            try:
                self.raise_(); self.activateWindow(); self.show()
            except Exception:
                pass
        self.update()

    def _follow_cursor_screen(self):
        """定时检查鼠标所在屏幕并切换覆盖，拖拽中不切屏。"""
        # 窗口不可见或正在拖拽时不做任何切换
        if self._closing or not self.isVisible() or self._dragging:
            return
        pos = QtGui.QCursor.pos()
        scr = QtGui.QGuiApplication.screenAt(pos)
        # 兼容回退：若screenAt返回None，手动根据geometry判断
        if scr is None:
            for s in QtGui.QGuiApplication.screens():
                if s.geometry().contains(pos):
                    scr = s
                    break
        if scr is not None and scr is not self._screen:
            self._switch_to_screen(scr)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        p = QtGui.QPainter(self)
        # 绘制屏幕截图作为背景
        p.drawPixmap(0, 0, self.width(), self.height(), self._bg)
        # 半透明遮罩
        p.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 100))
        # 选择区域高亮与尺寸提示
        if self._origin and self._current:
            rect = QtCore.QRect(self._origin, self._current).normalized()
            p.drawPixmap(rect, self._bg, rect)
            p.setPen(QtGui.QPen(QtGui.QColor(0, 120, 215), 2))
            p.setBrush(QtCore.Qt.NoBrush)
            p.drawRect(rect)
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
            p.setFont(self._hint_font)
            p.drawText(rect.adjusted(4, 4, -4, -4), QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, f"{rect.width()}x{rect.height()}")
        p.end()

    def mousePressEvent(self, e: QtGui.QMouseEvent) -> None:
        if e.button() == QtCore.Qt.LeftButton:
            self._dragging = True
            self._origin = e.pos()
            self._current = e.pos()
            self.update()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent) -> None:
        if self._origin:
            self._current = e.pos()
            self.update()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent) -> None:
        if e.button() == QtCore.Qt.LeftButton and self._origin and self._current:
            rect = QtCore.QRect(self._origin, self._current).normalized()
            if rect.width() > 2 and rect.height() > 2:
                # 处理高DPI，按设备像素比换算源区域
                dpr = self._bg.devicePixelRatio()
                src = QtCore.QRect(int(rect.x() * dpr), int(rect.y() * dpr), int(rect.width() * dpr), int(rect.height() * dpr))
                self.selected_pixmap = self._bg.copy(src)
            # 先结束拖拽，再accept，减少与定时器的竞态
            self._dragging = False
            self.accept()
        elif e.button() == QtCore.Qt.RightButton:
            self.reject()
        # 任意释放都结束拖拽
        self._dragging = False

    def keyPressEvent(self, e: QtGui.QKeyEvent) -> None:
        if e.key() == QtCore.Qt.Key_Escape:
            self.reject()
            self._dragging = False

def _parse_pair(text: str, typ=float) -> Tuple:
    """解析形如 "a,b" 的文本为二元组，允许空格。"""
    parts = [p.strip() for p in text.replace("；", ",").split(",") if p.strip()]
    if len(parts) != 2:
        raise ValueError("请输入两个以逗号分隔的数值")
    return typ(parts[0]), typ(parts[1])


def _parse_scales(text: str) -> Tuple[float, ...]:
    """解析倍率列表，如 "1.0,1.25,0.8"。"""
    parts = [p.strip() for p in text.replace("；", ",").split(",") if p.strip()]
    vals = []
    for p in parts:
        vals.append(float(p))
    if not vals:
        vals = [1.0]
    return tuple(vals)


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 窗口参数
        self.setWindowTitle("自动同意 - 设置")
        self.setModal(True)
        self.resize(860, 560)
        self.setMinimumSize(760, 520)

        # 载入配置
        self.cfg = load_config()

        # ============ 初始化控件（不立刻布局，后续分组放入页面）============
        # 模板列表（支持多图）
        self.list_templates = QtWidgets.QListWidget()
        self.list_templates.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        # 纵向滚动：禁用横向滚动并启用文本换行
        self.list_templates.setWordWrap(True)
        self.list_templates.setTextElideMode(QtCore.Qt.ElideNone)
        self.list_templates.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.list_templates.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.list_templates.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.list_templates.setResizeMode(QtWidgets.QListView.Adjust)
        self.list_templates.setUniformItemSizes(False)
        init_paths: List[str] = []
        if getattr(self.cfg, "template_paths", None):
            init_paths = list(self.cfg.template_paths)
        elif getattr(self.cfg, "template_path", None):
            if self.cfg.template_path:
                init_paths = [self.cfg.template_path]
        for p in init_paths:
            self.list_templates.addItem(p)
        self.btn_add_tpl = QtWidgets.QPushButton("添加图片…")
        self.btn_preview_tpl = QtWidgets.QPushButton("预览")
        self.btn_capture_tpl = QtWidgets.QPushButton("截图添加")
        self.btn_del_tpl = QtWidgets.QPushButton("删除选中")
        self.btn_clear_tpl = QtWidgets.QPushButton("清空列表")

        # 基本与性能
        self.sb_monitor = QtWidgets.QSpinBox(); self.sb_monitor.setRange(1, 16); self.sb_monitor.setValue(self.cfg.monitor_index); self.sb_monitor.setToolTip("mss监视器索引，1为主屏")
        self.sb_interval = QtWidgets.QSpinBox(); self.sb_interval.setRange(100, 10000); self.sb_interval.setSingleStep(50); self.sb_interval.setSuffix(" ms"); self.sb_interval.setValue(self.cfg.interval_ms); self.sb_interval.setToolTip("扫描间隔越大越省电")
        self.sb_min_det = QtWidgets.QSpinBox(); self.sb_min_det.setRange(1, 10); self.sb_min_det.setValue(self.cfg.min_detections)
        self.cb_auto_start = CustomCheckBox("启动后自动开始扫描"); self.cb_auto_start.setChecked(self.cfg.auto_start_scan)
        self.cb_logging = CustomCheckBox("启用日志到 log.txt"); self.cb_logging.setChecked(self.cfg.enable_logging)

        # 匹配参数
        self.ds_threshold = QtWidgets.QDoubleSpinBox(); self.ds_threshold.setRange(0.00, 1.00); self.ds_threshold.setSingleStep(0.01); self.ds_threshold.setDecimals(2); self.ds_threshold.setValue(self.cfg.threshold); self.ds_threshold.setToolTip("越大越严格，建议0.85~0.95")
        self.ds_cooldown = QtWidgets.QDoubleSpinBox(); self.ds_cooldown.setRange(0.0, 60.0); self.ds_cooldown.setSingleStep(0.5); self.ds_cooldown.setSuffix(" s"); self.ds_cooldown.setValue(self.cfg.cooldown_s); self.ds_cooldown.setToolTip("命中后冷却避免重复点击")
        self.cb_gray = CustomCheckBox("灰度匹配（更省电）"); self.cb_gray.setChecked(self.cfg.grayscale)
        self.cb_multiscale = CustomCheckBox("多尺度匹配"); self.cb_multiscale.setChecked(self.cfg.multi_scale)
        self.le_scales = QtWidgets.QLineEdit(",".join(f"{v:g}" for v in self.cfg.scales))
        self.le_scales.setPlaceholderText("示例：1.0,1.25,0.8（仅多尺度开启时生效）")
        self.le_scales.setToolTip("倍率列表按顺序尝试，建议包含1.0")

        # 点击与坐标
        self.le_offset = QtWidgets.QLineEdit(f"{self.cfg.click_offset[0]},{self.cfg.click_offset[1]}")
        self.le_offset.setPlaceholderText("示例：0,0 或 10,-6")
        self.le_offset.setToolTip("相对命中点的像素偏移，支持负数")
        self.cb_verify_window = CustomCheckBox("点击前验证窗口"); self.cb_verify_window.setChecked(self.cfg.verify_window_before_click)
        self.cb_coord_correction = CustomCheckBox("启用坐标校正"); self.cb_coord_correction.setChecked(self.cfg.enable_coordinate_correction)
        self.le_coord_offset = QtWidgets.QLineEdit(f"{self.cfg.coordinate_offset[0]},{self.cfg.coordinate_offset[1]}"); self.le_coord_offset.setPlaceholderText("示例：0,0")
        self.le_coord_offset.setToolTip("多屏校正时的全局坐标偏移")
        self.combo_click_method = QtWidgets.QComboBox(); self.combo_click_method.addItems(["message", "simulate"]); self.combo_click_method.setCurrentText(self.cfg.click_method)
        self.combo_transform_mode = QtWidgets.QComboBox(); self.combo_transform_mode.addItems(["auto", "manual", "disabled"]); self.combo_transform_mode.setCurrentText(self.cfg.coordinate_transform_mode)

        # 多屏幕
        self.cb_multi_screen_polling = CustomCheckBox("启用多屏幕轮询搜索"); self.cb_multi_screen_polling.setChecked(self.cfg.enable_multi_screen_polling)
        self.cb_multi_screen_polling.setToolTip("在所有屏幕上轮询搜索目标，适用于多屏幕环境")
        self.sb_polling_interval = QtWidgets.QSpinBox(); self.sb_polling_interval.setRange(500, 5000); self.sb_polling_interval.setSingleStep(100); self.sb_polling_interval.setSuffix(" ms"); self.sb_polling_interval.setValue(self.cfg.screen_polling_interval_ms)

        # ROI 编辑
        self.sb_roi_x = QtWidgets.QSpinBox(); self.sb_roi_x.setRange(0, 99999); self.sb_roi_x.setValue(self.cfg.roi.x)
        self.sb_roi_y = QtWidgets.QSpinBox(); self.sb_roi_y.setRange(0, 99999); self.sb_roi_y.setValue(self.cfg.roi.y)
        self.sb_roi_w = QtWidgets.QSpinBox(); self.sb_roi_w.setRange(0, 99999); self.sb_roi_w.setValue(self.cfg.roi.w)
        self.sb_roi_h = QtWidgets.QSpinBox(); self.sb_roi_h.setRange(0, 99999); self.sb_roi_h.setValue(self.cfg.roi.h)
        self.btn_roi_reset = QtWidgets.QPushButton("重置为整屏")

        # 调试
        self.cb_debug = CustomCheckBox("启用调试模式"); self.cb_debug.setChecked(self.cfg.debug_mode)
        self.cb_save_debug = CustomCheckBox("保存调试截图"); self.cb_save_debug.setChecked(self.cfg.save_debug_images)
        self.le_debug_dir = QtWidgets.QLineEdit(self.cfg.debug_image_dir)
        self.cb_enhanced_finding = CustomCheckBox("增强窗口查找"); self.cb_enhanced_finding.setChecked(self.cfg.enhanced_window_finding)

        # ============ 构建页面（右侧堆叠）============
        self.stack = QtWidgets.QStackedWidget()

        # — 常规 · 模板与启动
        page_general_tpl = QtWidgets.QWidget()
        vtpl = QtWidgets.QVBoxLayout(page_general_tpl)
        vtpl.setContentsMargins(16, 16, 16, 16)
        tpl_head = QtWidgets.QLabel("模板图片列表（支持多图，按优先级匹配）")
        tpl_head.setProperty("subtitle", True)
        vtpl.addWidget(tpl_head)
        vtpl.addWidget(self.list_templates, 1)
        tpl_btns = QtWidgets.QHBoxLayout()
        tpl_btns.addWidget(self.btn_add_tpl)
        tpl_btns.addWidget(self.btn_preview_tpl)
        tpl_btns.addWidget(self.btn_capture_tpl)
        tpl_btns.addWidget(self.btn_del_tpl)
        tpl_btns.addWidget(self.btn_clear_tpl)
        tpl_btns.addStretch(1)
        vtpl.addLayout(tpl_btns)
        vtpl.addSpacing(8)
        vtpl.addWidget(self.cb_auto_start)

        # — 常规 · 日志与显示器
        page_general_misc = QtWidgets.QWidget()
        form_misc = QtWidgets.QFormLayout(page_general_misc)
        form_misc.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        form_misc.setContentsMargins(16, 16, 16, 16)
        form_misc.addRow("显示器索引", self.sb_monitor)
        form_misc.addRow("扫描间隔", self.sb_interval)
        form_misc.addRow("最少命中帧", self.sb_min_det)
        form_misc.addRow(self.cb_logging)

        # — 匹配 · 参数与尺度
        page_match = QtWidgets.QWidget()
        form_match = QtWidgets.QFormLayout(page_match)
        form_match.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        form_match.setContentsMargins(16, 16, 16, 16)
        form_match.addRow("匹配阈值", self.ds_threshold)
        form_match.addRow("冷却时间", self.ds_cooldown)
        form_match.addRow("灰度匹配", self.cb_gray)
        form_match.addRow("多尺度匹配", self.cb_multiscale)
        form_match.addRow("倍率列表", self.le_scales)

        # — 点击 · 点击与坐标
        page_click = QtWidgets.QWidget()
        form_click = QtWidgets.QFormLayout(page_click)
        form_click.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        form_click.setContentsMargins(16, 16, 16, 16)
        form_click.addRow("点击偏移(dx,dy)", self.le_offset)
        form_click.addRow("点击方法", self.combo_click_method)
        form_click.addRow(self.cb_verify_window)
        form_click.addRow("坐标转换模式", self.combo_transform_mode)
        form_click.addRow(self.cb_coord_correction)
        form_click.addRow("坐标偏移(dx,dy)", self.le_coord_offset)

        # — 区域 · ROI
        page_roi = QtWidgets.QWidget()
        v_roi = QtWidgets.QVBoxLayout(page_roi)
        v_roi.setContentsMargins(16, 16, 16, 16)
        grid_roi = QtWidgets.QGridLayout()
        grid_roi.addWidget(QtWidgets.QLabel("X"), 0, 0)
        grid_roi.addWidget(self.sb_roi_x, 0, 1)
        grid_roi.addWidget(QtWidgets.QLabel("Y"), 0, 2)
        grid_roi.addWidget(self.sb_roi_y, 0, 3)
        grid_roi.addWidget(QtWidgets.QLabel("W"), 1, 0)
        grid_roi.addWidget(self.sb_roi_w, 1, 1)
        grid_roi.addWidget(QtWidgets.QLabel("H"), 1, 2)
        grid_roi.addWidget(self.sb_roi_h, 1, 3)
        grid_roi.addWidget(self.btn_roi_reset, 0, 4, 2, 1)
        gb_roi = QtWidgets.QGroupBox("ROI 区域（W/H=0 表示整屏）")
        gb_roi.setLayout(grid_roi)
        v_roi.addWidget(gb_roi)
        v_roi.addStretch(1)

        # — 多屏幕 · 轮询
        page_multi = QtWidgets.QWidget()
        form_multi = QtWidgets.QFormLayout(page_multi)
        form_multi.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        form_multi.setContentsMargins(16, 16, 16, 16)
        form_multi.addRow(self.cb_multi_screen_polling)
        form_multi.addRow("屏幕轮询间隔", self.sb_polling_interval)

        # — 调试 · 调试与输出
        page_debug = QtWidgets.QWidget()
        form_debug = QtWidgets.QFormLayout(page_debug)
        form_debug.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        form_debug.setContentsMargins(16, 16, 16, 16)
        form_debug.addRow(self.cb_debug)
        form_debug.addRow(self.cb_save_debug)
        form_debug.addRow("调试图片目录", self.le_debug_dir)
        form_debug.addRow(self.cb_enhanced_finding)

        # 加入堆叠
        pages = [page_general_tpl, page_general_misc, page_match, page_click, page_roi, page_multi, page_debug]
        for p in pages:
            self.stack.addWidget(p)

        # ============ 左侧多级菜单（QTreeWidget）============
        self.nav = QtWidgets.QTreeWidget()
        self.nav.setHeaderHidden(True)
        self.nav.setMaximumWidth(240)

        # 顶级：常规
        it_general = QtWidgets.QTreeWidgetItem(["常规"])
        it_general_tpl = QtWidgets.QTreeWidgetItem(["模板与启动"])
        it_general_tpl.setData(0, QtCore.Qt.ItemDataRole.UserRole, 0)
        it_general_misc = QtWidgets.QTreeWidgetItem(["日志与显示器"])
        it_general_misc.setData(0, QtCore.Qt.ItemDataRole.UserRole, 1)
        it_general.addChildren([it_general_tpl, it_general_misc])

        # 顶级：匹配
        it_match = QtWidgets.QTreeWidgetItem(["匹配"])
        it_match_param = QtWidgets.QTreeWidgetItem(["参数与尺度"])
        it_match_param.setData(0, QtCore.Qt.ItemDataRole.UserRole, 2)
        it_match.addChild(it_match_param)

        # 顶级：点击
        it_click = QtWidgets.QTreeWidgetItem(["点击"])
        it_click_main = QtWidgets.QTreeWidgetItem(["点击与坐标"])
        it_click_main.setData(0, QtCore.Qt.ItemDataRole.UserRole, 3)
        it_click.addChild(it_click_main)

        # 顶级：区域
        it_roi = QtWidgets.QTreeWidgetItem(["区域"])
        it_roi_page = QtWidgets.QTreeWidgetItem(["ROI 区域"])
        it_roi_page.setData(0, QtCore.Qt.ItemDataRole.UserRole, 4)
        it_roi.addChild(it_roi_page)

        # 顶级：多屏幕
        it_multi = QtWidgets.QTreeWidgetItem(["多屏幕"])
        it_multi_page = QtWidgets.QTreeWidgetItem(["轮询"])
        it_multi_page.setData(0, QtCore.Qt.ItemDataRole.UserRole, 5)
        it_multi.addChild(it_multi_page)

        # 顶级：调试
        it_debug = QtWidgets.QTreeWidgetItem(["调试"])
        it_debug_page = QtWidgets.QTreeWidgetItem(["调试与输出"])
        it_debug_page.setData(0, QtCore.Qt.ItemDataRole.UserRole, 6)
        it_debug.addChild(it_debug_page)

        self.nav.addTopLevelItems([it_general, it_match, it_click, it_roi, it_multi, it_debug])
        self.nav.expandAll()

        # ============ 总体布局（左右分栏 + 底部按钮）============
        splitter = QtWidgets.QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.nav)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        v = QtWidgets.QVBoxLayout(self)
        v.addWidget(splitter, 1)

        # 底部按钮区
        self.btn_ok = QtWidgets.QPushButton("保存")
        self.btn_ok.setObjectName("primary")
        self.btn_cancel = QtWidgets.QPushButton("取消")
        hb = QtWidgets.QHBoxLayout()
        hb.addStretch(1)
        hb.addWidget(self.btn_ok)
        hb.addWidget(self.btn_cancel)
        v.addLayout(hb)

        # 信号连接
        self.btn_add_tpl.clicked.connect(self._on_add_templates)
        self.btn_preview_tpl.clicked.connect(self._on_preview_template)
        self.btn_capture_tpl.clicked.connect(self._on_screenshot_add_template)
        self.btn_del_tpl.clicked.connect(self._on_remove_selected)
        self.btn_clear_tpl.clicked.connect(self._on_clear_templates)
        self.btn_roi_reset.clicked.connect(self._on_roi_reset)
        self.btn_ok.clicked.connect(self._on_save)
        self.btn_cancel.clicked.connect(self.reject)
        self.nav.currentItemChanged.connect(self._on_nav_changed)

        # 默认选择第一个子项
        self.nav.setCurrentItem(it_general_tpl)

    # ---------- 交互逻辑 ----------

    def _on_add_templates(self):
        """添加一个或多个模板图片到列表。"""
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "选择模板图片", os.getcwd(), "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not paths:
            return
        # 避免重复添加
        existing = set(self._get_template_paths())
        for p in paths:
            if p and p not in existing:
                self.list_templates.addItem(p)
                existing.add(p)

    def _on_remove_selected(self):
        """删除选中的模板路径。"""
        for item in self.list_templates.selectedItems():
            row = self.list_templates.row(item)
            self.list_templates.takeItem(row)

    def _on_clear_templates(self):
        """清空模板列表。"""
        self.list_templates.clear()

    def _ensure_assets_images_dir(self) -> Tuple[str, str]:
        """确保 assets/images 目录存在，返回(绝对路径, 相对路径)。"""
        proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        images_abs = os.path.join(proj_root, "assets", "images")
        images_rel = os.path.join("assets", "images")
        os.makedirs(images_abs, exist_ok=True)
        return images_abs, images_rel

    def _resolve_template_path(self, p: str) -> str:
        """解析模板条目的真实绝对路径。"""
        p = (p or "").strip()
        if not p:
            return ""
        if os.path.isabs(p) and os.path.exists(p):
            return p
        # 工作目录相对路径
        wd_path = os.path.abspath(os.path.join(os.getcwd(), p))
        if os.path.exists(wd_path):
            return wd_path
        # 项目根下的 assets/images
        images_abs, _ = self._ensure_assets_images_dir()
        candidate = os.path.join(images_abs, os.path.basename(p))
        if os.path.exists(candidate):
            return candidate
        # 项目根相对路径
        proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        other = os.path.abspath(os.path.join(proj_root, p))
        if os.path.exists(other):
            return other
        return p

    def _on_preview_template(self):
        """预览当前选中的模板图片。"""
        item = self.list_templates.selectedItems()[0] if self.list_templates.selectedItems() else self.list_templates.currentItem()
        if not item:
            QtWidgets.QMessageBox.information(self, "提示", "请先在列表中选择一张图片")
            return
        path = self._resolve_template_path(item.text())
        pm = QtGui.QPixmap(path)
        if pm.isNull():
            QtWidgets.QMessageBox.warning(self, "无法预览", f"图片无法打开：\n{path}")
            return
        ImagePreviewDialog(pm, path, self).exec()

    def _on_screenshot_add_template(self):
        """截图并在预览窗口中让用户决定是否保存为模板。

        改动说明：
        - 屏幕选择策略：优先使用鼠标所在屏幕，其次回退到“显示器索引”。
        - 截图完成后弹出“截图预览”对话框，提供“保存/取消”。
        - 用户点击保存时，统一保存为PNG到项目的 assets/images，并加入模板列表。
        """
        screens = QtGui.QGuiApplication.screens()
        if not screens:
            QtWidgets.QMessageBox.warning(self, "截图失败", "未检测到屏幕")
            return

        # 1) 优先根据鼠标位置选择屏幕；若不可用，回退到索引选择
        cursor_pos = QtGui.QCursor.pos()
        screen = QtGui.QGuiApplication.screenAt(cursor_pos)
        if screen is None:
            # 从“显示器索引”(1-based)选择屏幕（与旧行为兼容）
            idx = max(1, min(self.sb_monitor.value(), len(screens))) - 1
            screen = screens[idx]

        # 2) 截取目标屏幕全屏背景，启动区域取框
        bg = screen.grabWindow(0)
        snip = RegionSnipDialog(screen, bg, self)
        if snip.exec() != QtWidgets.QDialog.Accepted or not snip.selected_pixmap or snip.selected_pixmap.isNull():
            return

        # 3) 弹出确认预览，用户决定是否保存
        confirm = ScreenshotPreviewDialog(snip.selected_pixmap, self)
        if confirm.exec() != QtWidgets.QDialog.Accepted:
            # 用户取消，不保存
            return

        # 4) 保存PNG到 assets/images 下，并加入列表
        images_abs, images_rel = self._ensure_assets_images_dir()
        fname = f"template_{QtCore.QDateTime.currentDateTime().toString('yyyyMMdd_HHmmss_zzz')}.png"
        abs_path = os.path.join(images_abs, fname)
        snip.selected_pixmap.save(abs_path, "PNG")
        rel_path = os.path.join(images_rel, fname)
        self.list_templates.addItem(rel_path)
        QtWidgets.QMessageBox.information(self, "成功", f"模板图片已创建：\n{rel_path}")

    def _get_template_paths(self) -> List[str]:
        """读取列表中的所有模板路径。"""
        paths: List[str] = []
        for i in range(self.list_templates.count()):
            txt = self.list_templates.item(i).text().strip()
            if txt:
                paths.append(txt)
        return paths

    def _on_roi_reset(self):
        self.sb_roi_x.setValue(0)
        self.sb_roi_y.setValue(0)
        self.sb_roi_w.setValue(0)
        self.sb_roi_h.setValue(0)

    def _on_save(self):
        try:
            scales = _parse_scales(self.le_scales.text())
            dx, dy = _parse_pair(self.le_offset.text(), typ=float)
            coord_dx, coord_dy = _parse_pair(self.le_coord_offset.text(), typ=int)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "输入有误", str(e))
            return

        # 读取模板路径列表，若为空则给出提示但允许保存（将使用默认）
        tpl_paths = self._get_template_paths()
        if not tpl_paths:
            # 用户未配置则回退默认图片
            tpl_paths = []

        cfg = AppConfig(
            # 兼容：保留单模板字段，同时提供多模板列表
            template_path=(tpl_paths[0] if tpl_paths else "approve_pix.png"),
            template_paths=tpl_paths,
            monitor_index=self.sb_monitor.value(),
            roi=ROI(
                x=self.sb_roi_x.value(),
                y=self.sb_roi_y.value(),
                w=self.sb_roi_w.value(),
                h=self.sb_roi_h.value(),
            ),
            interval_ms=self.sb_interval.value(),
            threshold=self.ds_threshold.value(),
            cooldown_s=self.ds_cooldown.value(),
            enable_logging=self.cb_logging.isChecked(),
            grayscale=self.cb_gray.isChecked(),
            multi_scale=self.cb_multiscale.isChecked(),
            scales=scales,
            click_offset=(dx, dy),
            min_detections=self.sb_min_det.value(),
            auto_start_scan=self.cb_auto_start.isChecked(),
            # 新增的调试和多屏幕支持配置
            debug_mode=self.cb_debug.isChecked(),
            save_debug_images=self.cb_save_debug.isChecked(),
            debug_image_dir=self.le_debug_dir.text() or "debug_images",
            enable_coordinate_correction=self.cb_coord_correction.isChecked(),
            coordinate_offset=(coord_dx, coord_dy),
            enhanced_window_finding=self.cb_enhanced_finding.isChecked(),
            click_method=self.combo_click_method.currentText(),
            verify_window_before_click=self.cb_verify_window.isChecked(),
            coordinate_transform_mode=self.combo_transform_mode.currentText(),
            enable_multi_screen_polling=self.cb_multi_screen_polling.isChecked(),
            screen_polling_interval_ms=self.sb_polling_interval.value(),
        )
        save_config(cfg)
        self.accept()

    def _on_nav_changed(self, cur: QtWidgets.QTreeWidgetItem, prev: QtWidgets.QTreeWidgetItem | None):
        """左侧菜单变化时切换到对应页面。"""
        if not cur:
            return
        page_index = cur.data(0, QtCore.Qt.ItemDataRole.UserRole)
        # 若点击的是父节点，则默认跳转到第一个子节点
        if page_index is None and cur.childCount() > 0:
            child = cur.child(0)
            self.nav.setCurrentItem(child)
            return
        if isinstance(page_index, int):
            self.stack.setCurrentIndex(page_index)

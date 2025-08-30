# -*- coding: utf-8 -*-
"""
设置对话框：允许用户配置模板路径、阈值、扫描间隔、ROI、显示器索引、冷却时间、
灰度/多尺度/缩放倍率、点击偏移、最少命中帧、启动即扫描与日志开关，并保存到 JSON。
"""
from __future__ import annotations
import os
from typing import Tuple, List

from PySide6 import QtWidgets, QtCore

from config_manager import AppConfig, ROI, save_config, load_config


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
        init_paths: List[str] = []
        if getattr(self.cfg, "template_paths", None):
            init_paths = list(self.cfg.template_paths)
        elif getattr(self.cfg, "template_path", None):
            if self.cfg.template_path:
                init_paths = [self.cfg.template_path]
        for p in init_paths:
            self.list_templates.addItem(p)
        self.btn_add_tpl = QtWidgets.QPushButton("添加图片…")
        self.btn_del_tpl = QtWidgets.QPushButton("删除选中")
        self.btn_clear_tpl = QtWidgets.QPushButton("清空列表")

        # 基本与性能
        self.sb_monitor = QtWidgets.QSpinBox(); self.sb_monitor.setRange(1, 16); self.sb_monitor.setValue(self.cfg.monitor_index); self.sb_monitor.setToolTip("mss监视器索引，1为主屏")
        self.sb_interval = QtWidgets.QSpinBox(); self.sb_interval.setRange(100, 10000); self.sb_interval.setSingleStep(50); self.sb_interval.setSuffix(" ms"); self.sb_interval.setValue(self.cfg.interval_ms); self.sb_interval.setToolTip("扫描间隔越大越省电")
        self.sb_min_det = QtWidgets.QSpinBox(); self.sb_min_det.setRange(1, 10); self.sb_min_det.setValue(self.cfg.min_detections)
        self.cb_auto_start = QtWidgets.QCheckBox("启动后自动开始扫描"); self.cb_auto_start.setChecked(self.cfg.auto_start_scan)
        self.cb_logging = QtWidgets.QCheckBox("启用日志到 log.txt"); self.cb_logging.setChecked(self.cfg.enable_logging)

        # 匹配参数
        self.ds_threshold = QtWidgets.QDoubleSpinBox(); self.ds_threshold.setRange(0.00, 1.00); self.ds_threshold.setSingleStep(0.01); self.ds_threshold.setDecimals(2); self.ds_threshold.setValue(self.cfg.threshold); self.ds_threshold.setToolTip("越大越严格，建议0.85~0.95")
        self.ds_cooldown = QtWidgets.QDoubleSpinBox(); self.ds_cooldown.setRange(0.0, 60.0); self.ds_cooldown.setSingleStep(0.5); self.ds_cooldown.setSuffix(" s"); self.ds_cooldown.setValue(self.cfg.cooldown_s); self.ds_cooldown.setToolTip("命中后冷却避免重复点击")
        self.cb_gray = QtWidgets.QCheckBox("灰度匹配（更省电）"); self.cb_gray.setChecked(self.cfg.grayscale)
        self.cb_multiscale = QtWidgets.QCheckBox("多尺度匹配"); self.cb_multiscale.setChecked(self.cfg.multi_scale)
        self.le_scales = QtWidgets.QLineEdit(",".join(f"{v:g}" for v in self.cfg.scales))
        self.le_scales.setPlaceholderText("示例：1.0,1.25,0.8（仅多尺度开启时生效）")
        self.le_scales.setToolTip("倍率列表按顺序尝试，建议包含1.0")

        # 点击与坐标
        self.le_offset = QtWidgets.QLineEdit(f"{self.cfg.click_offset[0]},{self.cfg.click_offset[1]}")
        self.le_offset.setPlaceholderText("示例：0,0 或 10,-6")
        self.le_offset.setToolTip("相对命中点的像素偏移，支持负数")
        self.cb_verify_window = QtWidgets.QCheckBox("点击前验证窗口"); self.cb_verify_window.setChecked(self.cfg.verify_window_before_click)
        self.cb_coord_correction = QtWidgets.QCheckBox("启用坐标校正"); self.cb_coord_correction.setChecked(self.cfg.enable_coordinate_correction)
        self.le_coord_offset = QtWidgets.QLineEdit(f"{self.cfg.coordinate_offset[0]},{self.cfg.coordinate_offset[1]}"); self.le_coord_offset.setPlaceholderText("示例：0,0")
        self.le_coord_offset.setToolTip("多屏校正时的全局坐标偏移")
        self.combo_click_method = QtWidgets.QComboBox(); self.combo_click_method.addItems(["message", "simulate"]); self.combo_click_method.setCurrentText(self.cfg.click_method)
        self.combo_transform_mode = QtWidgets.QComboBox(); self.combo_transform_mode.addItems(["auto", "manual", "disabled"]); self.combo_transform_mode.setCurrentText(self.cfg.coordinate_transform_mode)

        # 多屏幕
        self.cb_multi_screen_polling = QtWidgets.QCheckBox("启用多屏幕轮询搜索"); self.cb_multi_screen_polling.setChecked(self.cfg.enable_multi_screen_polling)
        self.cb_multi_screen_polling.setToolTip("在所有屏幕上轮询搜索目标，适用于多屏幕环境")
        self.sb_polling_interval = QtWidgets.QSpinBox(); self.sb_polling_interval.setRange(500, 5000); self.sb_polling_interval.setSingleStep(100); self.sb_polling_interval.setSuffix(" ms"); self.sb_polling_interval.setValue(self.cfg.screen_polling_interval_ms)

        # ROI 编辑
        self.sb_roi_x = QtWidgets.QSpinBox(); self.sb_roi_x.setRange(0, 99999); self.sb_roi_x.setValue(self.cfg.roi.x)
        self.sb_roi_y = QtWidgets.QSpinBox(); self.sb_roi_y.setRange(0, 99999); self.sb_roi_y.setValue(self.cfg.roi.y)
        self.sb_roi_w = QtWidgets.QSpinBox(); self.sb_roi_w.setRange(0, 99999); self.sb_roi_w.setValue(self.cfg.roi.w)
        self.sb_roi_h = QtWidgets.QSpinBox(); self.sb_roi_h.setRange(0, 99999); self.sb_roi_h.setValue(self.cfg.roi.h)
        self.btn_roi_reset = QtWidgets.QPushButton("重置为整屏")

        # 调试
        self.cb_debug = QtWidgets.QCheckBox("启用调试模式"); self.cb_debug.setChecked(self.cfg.debug_mode)
        self.cb_save_debug = QtWidgets.QCheckBox("保存调试截图"); self.cb_save_debug.setChecked(self.cfg.save_debug_images)
        self.le_debug_dir = QtWidgets.QLineEdit(self.cfg.debug_image_dir)
        self.cb_enhanced_finding = QtWidgets.QCheckBox("增强窗口查找"); self.cb_enhanced_finding.setChecked(self.cfg.enhanced_window_finding)

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

# -*- coding: utf-8 -*-
"""
屏幕列表显示对话框
显示系统中检测到的所有屏幕信息，包括分辨率、位置等详细信息
"""

from PySide6 import QtWidgets, QtCore, QtGui
from capture import get_all_monitors_info


class ScreenListDialog(QtWidgets.QDialog):
    """屏幕列表显示对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("检测到的屏幕列表")
        self.setModal(True)
        self.resize(600, 400)
        
        # 设置窗口图标
        self.setWindowIcon(self._create_screen_icon())
        
        self._setup_ui()
        self._load_screen_info()
    
    def _create_screen_icon(self) -> QtGui.QIcon:
        """创建屏幕图标"""
        pixmap = QtGui.QPixmap(16, 16)
        pixmap.fill(QtGui.QColor("#4A90E2"))  # 蓝色背景
        
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # 绘制屏幕边框
        painter.setPen(QtGui.QPen(QtGui.QColor("#2C5282"), 1))
        painter.setBrush(QtGui.QBrush(QtGui.QColor("#4A90E2")))
        painter.drawRect(2, 3, 12, 8)
        
        # 绘制屏幕底座
        painter.drawRect(6, 11, 4, 2)
        painter.drawRect(4, 13, 8, 1)
        
        painter.end()
        return QtGui.QIcon(pixmap)
    
    def _setup_ui(self):
        """设置用户界面"""
        layout = QtWidgets.QVBoxLayout(self)
        
        # 标题标签
        title_label = QtWidgets.QLabel("系统检测到的屏幕列表")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # 屏幕信息表格
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "屏幕编号", "分辨率", "位置 (X, Y)", "尺寸 (宽×高)", "是否主屏", "状态"
        ])
        
        # 设置表格样式
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(True)
        self.table.setGridStyle(QtCore.Qt.SolidLine)
        
        # 设置列宽 - 更合理的分配
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(QtCore.Qt.AlignCenter)  # 表头居中对齐
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.Stretch)  # 状态列自适应
        
        self.table.setColumnWidth(0, 70)   # 屏幕编号 - 稍微缩小
        self.table.setColumnWidth(1, 110)  # 分辨率 - 稍微缩小
        self.table.setColumnWidth(2, 110)  # 位置 - 稍微缩小
        self.table.setColumnWidth(3, 110)  # 尺寸 - 稍微缩小
        self.table.setColumnWidth(4, 75)   # 是否主屏 - 稍微缩小
        
        # 设置垂直表头
        vertical_header = self.table.verticalHeader()
        vertical_header.setDefaultSectionSize(28)  # 行高
        vertical_header.setVisible(False)  # 隐藏行号
        
        layout.addWidget(self.table)
        
        # 信息标签
        self.info_label = QtWidgets.QLabel()
        self.info_label.setStyleSheet("color: #666; font-size: 12px; margin-top: 10px;")
        layout.addWidget(self.info_label)
        
        # 按钮区域
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(8)  # 设置按钮间距
        button_layout.setContentsMargins(16, 12, 16, 12)  # 设置布局边距
        
        # 刷新按钮
        refresh_btn = QtWidgets.QPushButton("刷新")
        refresh_btn.clicked.connect(self._load_screen_info)
        refresh_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        button_layout.addWidget(refresh_btn)
        
        button_layout.addStretch()
        
        # 关闭按钮
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _load_screen_info(self):
        """加载屏幕信息"""
        try:
            # 使用WGC获取显示器信息
            monitors_info = get_all_monitors_info()

            # 清空表格
            self.table.setRowCount(0)
            self.table.setRowCount(len(monitors_info))
                
            for i, monitor_info in enumerate(monitors_info):
                # 屏幕编号
                screen_num_item = QtWidgets.QTableWidgetItem(str(monitor_info['index']))
                screen_num_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(i, 0, screen_num_item)

                # 分辨率
                resolution = f"{monitor_info['width']}×{monitor_info['height']}"
                resolution_item = QtWidgets.QTableWidgetItem(resolution)
                resolution_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(i, 1, resolution_item)

                # 位置
                position = f"({monitor_info['left']}, {monitor_info['top']})"
                position_item = QtWidgets.QTableWidgetItem(position)
                position_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(i, 2, position_item)

                # 尺寸（重复显示，便于查看）
                size = f"{monitor_info['width']}×{monitor_info['height']}"
                size_item = QtWidgets.QTableWidgetItem(size)
                size_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(i, 3, size_item)

                # 是否主屏
                is_primary = "是" if monitor_info['is_primary'] else "否"
                primary_item = QtWidgets.QTableWidgetItem(is_primary)
                primary_item.setTextAlignment(QtCore.Qt.AlignCenter)
                if is_primary == "是":
                    primary_item.setBackground(QtGui.QColor("#E8F5E8"))
                    primary_item.setForeground(QtGui.QColor("#2E7D32"))
                self.table.setItem(i, 4, primary_item)

                # 状态
                status = "正常"
                status_item = QtWidgets.QTableWidgetItem(status)
                status_item.setTextAlignment(QtCore.Qt.AlignCenter)
                status_item.setBackground(QtGui.QColor("#E8F5E8"))
                status_item.setForeground(QtGui.QColor("#2E7D32"))
                self.table.setItem(i, 5, status_item)
                
                # 更新信息标签
                total_screens = len(actual_monitors)
                virtual_screen = monitors[0]
                total_width = virtual_screen['width']
                total_height = virtual_screen['height']
                
                info_text = (f"共检测到 {total_screens} 个屏幕，"
                           f"虚拟桌面总尺寸：{total_width}×{total_height} 像素")
                self.info_label.setText(info_text)
                
        except Exception as e:
            # 错误处理
            QtWidgets.QMessageBox.warning(
                self, "错误", 
                f"获取屏幕信息时发生错误：\n{str(e)}"
            )
            self.info_label.setText("获取屏幕信息失败")
    
    def get_selected_screen(self) -> int:
        """获取用户选择的屏幕编号（1开始）"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            return current_row + 1
        return 1  # 默认返回第一个屏幕


def show_screen_list_dialog(parent=None) -> int:
    """显示屏幕列表对话框并返回选择的屏幕编号"""
    dialog = ScreenListDialog(parent)
    dialog.exec()
    return dialog.get_selected_screen()


if __name__ == "__main__":
    # 测试代码
    import sys
    app = QtWidgets.QApplication(sys.argv)
    
    selected_screen = show_screen_list_dialog()
    print(f"选择的屏幕编号: {selected_screen}")
    
    sys.exit(app.exec())
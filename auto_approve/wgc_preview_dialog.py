# -*- coding: utf-8 -*-
"""
WGC实时预览对话框
提供实时窗口捕获预览功能，方便用户验证WGC配置效果
"""

import time
import numpy as np
import cv2
from PySide6 import QtWidgets, QtCore, QtGui
from typing import Optional


class WGCPreviewDialog(QtWidgets.QDialog):
    """WGC实时预览对话框"""
    
    def __init__(self, hwnd: int, parent=None, *, fps: int = 15, include_cursor: bool = False, border_required: bool = False):
        super().__init__(parent)
        self.hwnd = hwnd
        self.capture_manager = None
        self.timer = None
        self.is_capturing = False
        # 预览配置（从外部传入，确保与设置面板一致）
        self.preview_fps = max(1, min(int(fps), 60))
        self.include_cursor = bool(include_cursor)
        self.border_required = bool(border_required)
        
        self.setWindowTitle(f"WGC实时预览 - HWND: {hwnd}")
        self.resize(800, 600)
        self.setModal(True)
        
        self._setup_ui()
        self._setup_capture()
        
    def _setup_ui(self):
        """设置UI界面"""
        layout = QtWidgets.QVBoxLayout(self)
        
        # 顶部信息栏
        info_layout = QtWidgets.QHBoxLayout()
        
        self.info_label = QtWidgets.QLabel(f"目标窗口: HWND {self.hwnd}")
        self.info_label.setStyleSheet("font-weight: bold; color: #2F80ED;")
        info_layout.addWidget(self.info_label)
        
        info_layout.addStretch()
        
        self.fps_label = QtWidgets.QLabel("FPS: --")
        info_layout.addWidget(self.fps_label)
        
        self.size_label = QtWidgets.QLabel("尺寸: --")
        info_layout.addWidget(self.size_label)
        
        layout.addLayout(info_layout)
        
        # 预览区域
        self.preview_label = QtWidgets.QLabel()
        self.preview_label.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_label.setMinimumSize(400, 300)
        self.preview_label.setStyleSheet("""
            QLabel {
                border: 2px solid #E0E0E0;
                background-color: #F5F5F5;
                border-radius: 4px;
            }
        """)
        self.preview_label.setText("正在初始化预览...")
        
        # 将预览标签放在滚动区域中
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidget(self.preview_label)
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(QtCore.Qt.AlignCenter)
        
        layout.addWidget(scroll_area, 1)
        
        # 控制按钮
        control_layout = QtWidgets.QHBoxLayout()
        
        self.start_btn = QtWidgets.QPushButton("开始预览")
        self.start_btn.clicked.connect(self._start_preview)
        control_layout.addWidget(self.start_btn)
        
        self.stop_btn = QtWidgets.QPushButton("停止预览")
        self.stop_btn.clicked.connect(self._stop_preview)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)
        
        control_layout.addStretch()
        
        self.save_btn = QtWidgets.QPushButton("保存当前帧")
        self.save_btn.clicked.connect(self._save_current_frame)
        self.save_btn.setEnabled(False)
        control_layout.addWidget(self.save_btn)
        
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        control_layout.addWidget(close_btn)
        
        layout.addLayout(control_layout)
        
        # 状态栏
        self.status_label = QtWidgets.QLabel("就绪")
        self.status_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.status_label)
        
        # 用于FPS计算
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.current_frame = None
        
    def _setup_capture(self):
        """设置捕获管理器"""
        try:
            from capture import CaptureManager
            self.capture_manager = CaptureManager()
            
            # 配置参数：使用外部传入的光标/边框开关，确保与设置勾选一致
            self.capture_manager.configure(
                fps=self.preview_fps,  # 预览使用较低帧率
                include_cursor=self.include_cursor,
                border_required=self.border_required,
                restore_minimized=True
            )
            
            self.status_label.setText("捕获管理器初始化成功")
            
        except Exception as e:
            self.status_label.setText(f"初始化失败: {e}")
            QtWidgets.QMessageBox.critical(self, "错误", f"初始化捕获管理器失败: {e}")
    
    def _start_preview(self):
        """开始预览"""
        if not self.capture_manager:
            return
            
        try:
            # 打开窗口捕获
            success = self.capture_manager.open_window(self.hwnd)
            if not success:
                QtWidgets.QMessageBox.warning(self, "失败", "无法启动窗口捕获")
                return
            
            # 设置定时器
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self._capture_frame)
            self.timer.start(66)  # 约15 FPS
            
            self.is_capturing = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.save_btn.setEnabled(True)
            
            self.status_label.setText("预览中...")
            
        except Exception as e:
            self.status_label.setText(f"启动失败: {e}")
            QtWidgets.QMessageBox.critical(self, "错误", f"启动预览失败: {e}")
    
    def _stop_preview(self):
        """停止预览"""
        if self.timer:
            self.timer.stop()
            self.timer = None
        
        if self.capture_manager:
            self.capture_manager.close()
        
        self.is_capturing = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        
        self.status_label.setText("已停止")
        self.preview_label.setText("预览已停止")
    
    def _capture_frame(self):
        """捕获并显示一帧"""
        if not self.capture_manager or not self.is_capturing:
            return
            
        try:
            # 捕获帧
            frame = self.capture_manager.capture_frame()
            if frame is None:
                return
            
            self.current_frame = frame
            h, w = frame.shape[:2]
            
            # 更新尺寸信息
            self.size_label.setText(f"尺寸: {w}×{h}")
            
            # 计算FPS
            self.frame_count += 1
            current_time = time.time()
            if current_time - self.last_fps_time >= 1.0:
                fps = self.frame_count / (current_time - self.last_fps_time)
                self.fps_label.setText(f"FPS: {fps:.1f}")
                self.frame_count = 0
                self.last_fps_time = current_time
            
            # 转换为Qt图像并显示
            self._display_frame(frame)
            
        except Exception as e:
            self.status_label.setText(f"捕获错误: {e}")
    
    def _display_frame(self, frame):
        """显示帧到预览标签"""
        try:
            h, w = frame.shape[:2]
            
            # 确保图像数据连续
            if not frame.flags['C_CONTIGUOUS']:
                frame = np.ascontiguousarray(frame)
            
            # BGR转RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # 创建QImage
            bytes_per_line = rgb.strides[0] if rgb.strides else w * 3
            qimg = QtGui.QImage(rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
            
            if qimg.isNull():
                return
            
            # 创建像素图并缩放到合适大小
            pixmap = QtGui.QPixmap.fromImage(qimg)
            if pixmap.isNull():
                return
            
            # 缩放到预览标签大小，保持宽高比
            label_size = self.preview_label.size()
            scaled_pixmap = pixmap.scaled(
                label_size, 
                QtCore.Qt.KeepAspectRatio, 
                QtCore.Qt.SmoothTransformation
            )
            
            self.preview_label.setPixmap(scaled_pixmap)
            
        except Exception as e:
            self.status_label.setText(f"显示错误: {e}")
    
    def _save_current_frame(self):
        """保存当前帧"""
        if self.current_frame is None:
            QtWidgets.QMessageBox.warning(self, "提示", "没有可保存的帧")
            return
        
        try:
            timestamp = int(time.time())
            filename = f"wgc_preview_capture_{timestamp}.png"
            
            success = cv2.imwrite(filename, self.current_frame)
            if success:
                QtWidgets.QMessageBox.information(self, "成功", f"图片已保存: {filename}")
            else:
                QtWidgets.QMessageBox.warning(self, "失败", "保存图片失败")
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"保存失败: {e}")
    
    def closeEvent(self, event):
        """关闭事件"""
        self._stop_preview()
        super().closeEvent(event)
    
    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        # 如果有当前帧，重新显示以适应新尺寸
        if self.current_frame is not None:
            self._display_frame(self.current_frame)

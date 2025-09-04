# -*- coding: utf-8 -*-
"""
UI增强模块 - 提供动画效果、响应式布局和视觉增强功能
"""
from __future__ import annotations
from PySide6 import QtWidgets, QtCore, QtGui


class UIEnhancementManager:
    """UI增强管理器 - 提供统一的UI增强功能（优化版本）"""

    # 全局动画控制开关
    _animations_enabled = True

    @classmethod
    def set_animations_enabled(cls, enabled: bool):
        """设置是否启用动画效果"""
        cls._animations_enabled = enabled

    @staticmethod
    def _cleanup_widget_animations(widget: QtWidgets.QWidget):
        """清理控件上的动画和效果，防止内存泄漏"""
        # 清理淡入动画
        if hasattr(widget, '_fade_animation'):
            animation = getattr(widget, '_fade_animation')
            if animation and animation.state() == QtCore.QAbstractAnimation.Running:
                animation.stop()
            delattr(widget, '_fade_animation')

        # 清理滑入动画
        if hasattr(widget, '_slide_animation'):
            animation = getattr(widget, '_slide_animation')
            if animation and animation.state() == QtCore.QAbstractAnimation.Running:
                animation.stop()
            delattr(widget, '_slide_animation')

        # 清理其他动画
        for attr_name in ['_hover_animation', '_scale_animation', '_rotation_animation']:
            if hasattr(widget, attr_name):
                animation = getattr(widget, attr_name)
                if animation and animation.state() == QtCore.QAbstractAnimation.Running:
                    animation.stop()
                delattr(widget, attr_name)

    @staticmethod
    def _cleanup_widget_animations(widget: QtWidgets.QWidget):
        """清理控件上的动画和效果，防止内存泄漏"""
        # 清理淡入动画
        if hasattr(widget, '_fade_animation'):
            animation = getattr(widget, '_fade_animation')
            if animation and animation.state() == QtCore.QAbstractAnimation.Running:
                animation.stop()
            delattr(widget, '_fade_animation')

        # 清理滑入动画
        if hasattr(widget, '_slide_animation'):
            animation = getattr(widget, '_slide_animation')
            if animation and animation.state() == QtCore.QAbstractAnimation.Running:
                animation.stop()
            delattr(widget, '_slide_animation')

        # 清理其他动画
        for attr_name in ['_hover_animation', '_scale_animation', '_rotation_animation']:
            if hasattr(widget, attr_name):
                animation = getattr(widget, attr_name)
                if animation and animation.state() == QtCore.QAbstractAnimation.Running:
                    animation.stop()
                delattr(widget, attr_name)

    @staticmethod
    def apply_fade_in_animation(widget: QtWidgets.QWidget, duration: int = 150):
        """为控件添加淡入动画效果（优化版本，减少动画开销）"""
        # 检查是否启用动画（可通过配置控制）
        if not getattr(UIEnhancementManager, '_animations_enabled', True):
            return

        # 清理之前的动画和效果
        UIEnhancementManager._cleanup_widget_animations(widget)

        # 使用更轻量的动画实现
        effect = QtWidgets.QGraphicsOpacityEffect()
        widget.setGraphicsEffect(effect)

        animation = QtCore.QPropertyAnimation(effect, b"opacity")
        animation.setDuration(duration)  # 减少动画时长
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QtCore.QEasingCurve.OutQuad)  # 使用更简单的缓动

        # 动画完成后自动清理
        def cleanup_animation():
            try:
                if hasattr(widget, '_fade_animation'):
                    delattr(widget, '_fade_animation')
                # 移除图形效果以释放内存
                widget.setGraphicsEffect(None)
            except Exception:
                pass  # 忽略清理错误

        animation.finished.connect(cleanup_animation)
        animation.start()

        # 保持动画引用，防止被垃圾回收
        widget._fade_animation = animation
    
    @staticmethod
    def apply_slide_in_animation(widget: QtWidgets.QWidget, direction: str = "up", duration: int = 400):
        """为控件添加滑入动画效果（带内存泄漏修复）

        Args:
            widget: 目标控件
            direction: 滑入方向 ("up", "down", "left", "right")
            duration: 动画持续时间（毫秒）
        """
        # 清理之前的动画
        UIEnhancementManager._cleanup_widget_animations(widget)

        original_pos = widget.pos()

        # 计算起始位置
        if direction == "up":
            start_pos = QtCore.QPoint(original_pos.x(), original_pos.y() + 50)
        elif direction == "down":
            start_pos = QtCore.QPoint(original_pos.x(), original_pos.y() - 50)
        elif direction == "left":
            start_pos = QtCore.QPoint(original_pos.x() + 50, original_pos.y())
        else:  # right
            start_pos = QtCore.QPoint(original_pos.x() - 50, original_pos.y())

        widget.move(start_pos)

        animation = QtCore.QPropertyAnimation(widget, b"pos")
        animation.setDuration(duration)
        animation.setStartValue(start_pos)
        animation.setEndValue(original_pos)
        animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        # 动画完成后自动清理
        def cleanup_animation():
            if hasattr(widget, '_slide_animation'):
                delattr(widget, '_slide_animation')

        animation.finished.connect(cleanup_animation)
        animation.start()

        widget._slide_animation = animation
    
    @staticmethod
    def apply_button_hover_effect(button: QtWidgets.QPushButton):
        """为按钮添加悬停效果"""
        original_style = button.styleSheet()
        
        def on_enter():
            button.setStyleSheet(original_style + """
                QPushButton {
                    /* Qt样式表不支持transform和transition属性 */
                    background-color: rgba(255, 255, 255, 0.1);
                }
            """)
        
        def on_leave():
            button.setStyleSheet(original_style)
        
        button.enterEvent = lambda event: on_enter()
        button.leaveEvent = lambda event: on_leave()
    
    @staticmethod
    def apply_shadow_effect(widget: QtWidgets.QWidget, blur_radius: int = 10, 
                           offset: tuple = (2, 2), color: QtGui.QColor = None):
        """为控件添加阴影效果"""
        if color is None:
            color = QtGui.QColor(0, 0, 0, 80)
        
        shadow = QtWidgets.QGraphicsDropShadowEffect()
        shadow.setBlurRadius(blur_radius)
        shadow.setOffset(offset[0], offset[1])
        shadow.setColor(color)
        widget.setGraphicsEffect(shadow)
    
    @staticmethod
    def make_responsive_layout(layout: QtWidgets.QLayout, min_width: int = 400):
        """使布局响应式 - 根据窗口大小调整布局"""
        if isinstance(layout, QtWidgets.QGridLayout):
            # 网格布局响应式处理
            def adjust_grid():
                widget = layout.parentWidget()
                if widget and widget.width() < min_width:
                    # 小屏幕时改为单列布局
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item and item.widget():
                            row, col, rowspan, colspan = layout.getItemPosition(i)
                            if col > 0:
                                layout.addWidget(item.widget(), row + col, 0)
            
            return adjust_grid
        
        elif isinstance(layout, QtWidgets.QHBoxLayout):
            # 水平布局响应式处理
            def adjust_horizontal():
                widget = layout.parentWidget()
                if widget and widget.width() < min_width:
                    # 小屏幕时改为垂直布局
                    items = []
                    while layout.count():
                        item = layout.takeAt(0)
                        if item and item.widget():
                            items.append(item.widget())
                    
                    # 创建垂直布局
                    v_layout = QtWidgets.QVBoxLayout()
                    for item_widget in items:
                        v_layout.addWidget(item_widget)
                    
                    # 替换布局
                    if widget.layout():
                        QtWidgets.QWidget().setLayout(widget.layout())
                    widget.setLayout(v_layout)
            
            return adjust_horizontal
        
        return None
    
    @staticmethod
    def apply_smooth_scroll(scroll_area: QtWidgets.QScrollArea):
        """为滚动区域添加平滑滚动效果"""
        scroll_bar = scroll_area.verticalScrollBar()
        
        def smooth_scroll_to(value):
            animation = QtCore.QPropertyAnimation(scroll_bar, b"value")
            animation.setDuration(300)
            animation.setStartValue(scroll_bar.value())
            animation.setEndValue(value)
            animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)
            animation.start()
            
            scroll_area._scroll_animation = animation
        
        # 重写滚轮事件
        original_wheel_event = scroll_area.wheelEvent
        
        def wheel_event(event):
            delta = event.angleDelta().y()
            current_value = scroll_bar.value()
            step = scroll_bar.singleStep() * 3
            
            if delta > 0:
                new_value = max(0, current_value - step)
            else:
                new_value = min(scroll_bar.maximum(), current_value + step)
            
            smooth_scroll_to(new_value)
            event.accept()
        
        scroll_area.wheelEvent = wheel_event
    
    @staticmethod
    def create_loading_spinner(parent: QtWidgets.QWidget = None, size: int = 32) -> QtWidgets.QLabel:
        """创建加载动画控件（优化版本，减少绘制开销）"""
        if not UIEnhancementManager._animations_enabled:
            # 如果禁用动画，返回简单的文本标签
            spinner = QtWidgets.QLabel("加载中...", parent)
            spinner.setAlignment(QtCore.Qt.AlignCenter)
            return spinner

        spinner = QtWidgets.QLabel(parent)
        spinner.setFixedSize(size, size)
        spinner.setAlignment(QtCore.Qt.AlignCenter)

        # 使用更简单的加载指示器
        spinner.setText("●")
        spinner.setStyleSheet(f"""
            QLabel {{
                color: #2F80ED;
                font-size: {size//2}px;
                font-weight: bold;
            }}
        """)

        # 简单的闪烁动画而不是旋转
        if hasattr(QtCore, 'QPropertyAnimation'):
            animation = QtCore.QPropertyAnimation(spinner, b"windowOpacity")
            animation.setDuration(1000)
            animation.setStartValue(0.3)
            animation.setEndValue(1.0)
            animation.setLoopCount(-1)  # 无限循环
            animation.start()
            spinner._loading_animation = animation
        
        # 创建旋转动画
        rotation = QtCore.QPropertyAnimation(spinner, b"rotation")
        rotation.setDuration(1000)
        rotation.setStartValue(0)
        rotation.setEndValue(360)
        rotation.setLoopCount(-1)  # 无限循环
        
        # 自定义旋转属性
        def set_rotation(angle):
            transform = QtGui.QTransform()
            transform.translate(size / 2, size / 2)
            transform.rotate(angle)
            transform.translate(-size / 2, -size / 2)
            spinner.setPixmap(pixmap.transformed(transform, QtCore.Qt.SmoothTransformation))
        
        spinner.set_rotation = set_rotation
        rotation.valueChanged.connect(set_rotation)
        
        spinner._rotation_animation = rotation
        
        def start_animation():
            rotation.start()
        
        def stop_animation():
            rotation.stop()
        
        spinner.start_animation = start_animation
        spinner.stop_animation = stop_animation
        
        return spinner
    
    @staticmethod
    def apply_window_effects(window: QtWidgets.QWidget):
        """为窗口应用现代化效果"""
        # 设置窗口属性
        window.setAttribute(QtCore.Qt.WA_TranslucentBackground, False)
        
        # 添加窗口阴影（仅在Windows上）
        try:
            import platform
            if platform.system() == "Windows":
                from ctypes import windll, c_int, byref
                hwnd = int(window.winId())
                
                # 启用窗口阴影
                windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 2, byref(c_int(2)), 4
                )
        except Exception:
            pass
        
        # 设置最小尺寸
        if hasattr(window, 'setMinimumSize'):
            window.setMinimumSize(400, 300)


def enhance_widget(widget: QtWidgets.QWidget, effects: list = None):
    """便捷函数：为控件应用多种增强效果
    
    Args:
        widget: 目标控件
        effects: 效果列表，可包含 "fade_in", "shadow", "hover" 等
    """
    if effects is None:
        effects = ["fade_in"]
    
    manager = UIEnhancementManager()
    
    for effect in effects:
        if effect == "fade_in":
            manager.apply_fade_in_animation(widget)
        elif effect == "shadow":
            manager.apply_shadow_effect(widget)
        elif effect == "hover" and isinstance(widget, QtWidgets.QPushButton):
            manager.apply_button_hover_effect(widget)
        elif effect == "window" and isinstance(widget, (QtWidgets.QDialog, QtWidgets.QMainWindow)):
            manager.apply_window_effects(widget)

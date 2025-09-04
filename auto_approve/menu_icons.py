# -*- coding: utf-8 -*-
"""
菜单图标管理器 - 为托盘菜单提供现代化图标支持
使用代码绘制图标，避免依赖外部图标文件，支持高DPI
"""
from __future__ import annotations
from PySide6 import QtGui, QtCore


class MenuIconManager:
    """菜单图标管理器 - 轻量级版本，减少内存占用"""

    _icon_cache = {}
    _max_cache_size = 10  # 限制缓存大小

    @classmethod
    def create_icon(cls, icon_type: str, size: int = 16, color: str = "#E6E6E6") -> QtGui.QIcon:
        """创建指定类型的图标

        Args:
            icon_type: 图标类型 (play, stop, settings, log, quit, status等)
            size: 图标尺寸
            color: 图标颜色

        Returns:
            QIcon对象
        """
        cache_key = f"{icon_type}_{size}_{color}"
        if cache_key in cls._icon_cache:
            return cls._icon_cache[cache_key]

        # 清理缓存以控制内存使用
        if len(cls._icon_cache) >= cls._max_cache_size:
            # 移除最旧的缓存项
            oldest_key = next(iter(cls._icon_cache))
            del cls._icon_cache[oldest_key]

        # 创建简化的图标（仅支持1x和2x DPI）
        icon = QtGui.QIcon()
        for scale in [1, 2]:  # 减少DPI支持以降低内存占用
            pixmap_size = int(size * scale)
            pixmap = cls._create_pixmap(icon_type, pixmap_size, color)
            if pixmap:
                pixmap.setDevicePixelRatio(scale)
                icon.addPixmap(pixmap)

        cls._icon_cache[cache_key] = icon
        return icon
    
    @classmethod
    def _create_pixmap(cls, icon_type: str, size: int, color: str) -> QtGui.QPixmap:
        """创建指定类型的像素图 - 现代化设计"""
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtCore.Qt.transparent)

        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)

        # 设置画笔和画刷 - 优化线条宽度适配更大图标
        pen = QtGui.QPen(QtGui.QColor(color))
        # 针对20px图标优化线条宽度：确保清晰度和视觉平衡
        pen.setWidth(max(1, size // 10))  # 从size//12调整为size//10，线条稍粗一些
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        painter.setPen(pen)

        brush = QtGui.QBrush(QtGui.QColor(color))
        painter.setBrush(brush)

        # 根据图标类型绘制 - 优化边距，提高图标在菜单中的视觉匹配度
        # 减少边距从 size//10 到 size//12，让图标更大更清晰
        margin = max(1, size // 12)  # 确保至少1像素边距
        rect = QtCore.QRect(margin, margin, size - 2 * margin, size - 2 * margin)
        
        try:
            if icon_type == "play":
                cls._draw_play_icon(painter, rect)
            elif icon_type == "stop":
                cls._draw_stop_icon(painter, rect)
            elif icon_type == "settings":
                cls._draw_settings_icon(painter, rect)
            elif icon_type == "log":
                cls._draw_log_icon(painter, rect)
            elif icon_type == "quit":
                cls._draw_quit_icon(painter, rect)
            elif icon_type == "status":
                cls._draw_status_icon(painter, rect)
            elif icon_type == "screen":
                cls._draw_screen_icon(painter, rect)
            elif icon_type == "check":
                cls._draw_check_icon(painter, rect)
            else:
                # 默认圆点图标
                painter.drawEllipse(rect)
        finally:
            painter.end()
        
        return pixmap
    
    @staticmethod
    def _draw_play_icon(painter: QtGui.QPainter, rect: QtCore.QRect):
        """绘制播放图标（现代化三角形）- 针对20px优化"""
        # 优化偏移量，使三角形在20px下更加居中和清晰
        offset_x = rect.width() // 6  # 减少水平偏移
        offset_y = rect.height() // 8  # 减少垂直边距
        points = [
            QtCore.QPoint(rect.left() + offset_x, rect.top() + offset_y),
            QtCore.QPoint(rect.left() + offset_x, rect.bottom() - offset_y),
            QtCore.QPoint(rect.right() - offset_x // 2, rect.center().y())
        ]

        # 使用渐变填充
        gradient = QtGui.QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0, painter.pen().color())
        gradient.setColorAt(1, painter.pen().color().darker(120))
        painter.setBrush(QtGui.QBrush(gradient))

        painter.drawPolygon(points)

    @staticmethod
    def _draw_stop_icon(painter: QtGui.QPainter, rect: QtCore.QRect):
        """绘制停止图标（现代化圆角方形）- 针对20px优化"""
        # 优化边距，使停止图标在20px下更加清晰
        margin = rect.width() // 8  # 减少边距，让图标更大
        stop_rect = rect.adjusted(margin, margin, -margin, -margin)

        # 使用渐变填充
        gradient = QtGui.QLinearGradient(stop_rect.topLeft(), stop_rect.bottomRight())
        gradient.setColorAt(0, painter.pen().color())
        gradient.setColorAt(1, painter.pen().color().darker(120))
        painter.setBrush(QtGui.QBrush(gradient))

        # 绘制圆角矩形，圆角半径适配20px
        corner_radius = max(1, rect.width() // 8)  # 动态圆角半径
        painter.drawRoundedRect(stop_rect, corner_radius, corner_radius)
    
    @staticmethod
    def _draw_settings_icon(painter: QtGui.QPainter, rect: QtCore.QRect):
        """绘制设置图标（现代化齿轮）- 针对20px优化"""
        center = rect.center()
        radius = min(rect.width(), rect.height()) // 2 - 1

        # 优化齿轮尺寸比例，适配20px
        outer_radius = radius * 0.85  # 稍微减小外圈
        inner_radius = radius * 0.45  # 调整内圈比例

        # 使用渐变填充
        gradient = QtGui.QRadialGradient(center, outer_radius)
        gradient.setColorAt(0, painter.pen().color().lighter(110))
        gradient.setColorAt(1, painter.pen().color())
        painter.setBrush(QtGui.QBrush(gradient))

        # 绘制齿轮齿 - 简化为6个齿，在20px下更清晰
        painter.save()
        painter.translate(center)

        # 创建齿轮路径
        path = QtGui.QPainterPath()

        for i in range(6):  # 减少到6个齿
            angle = i * 60  # 60度间隔
            painter.save()
            painter.rotate(angle)

            # 优化齿轮齿尺寸，适配20px
            tooth_width = max(2, rect.width() // 8)  # 动态齿宽
            tooth_height = outer_radius * 0.3  # 齿高
            tooth_rect = QtCore.QRectF(-tooth_width/2, -outer_radius, tooth_width, tooth_height)
            path.addRoundedRect(tooth_rect, 0.5, 0.5)
            painter.restore()

        # 绘制齿轮主体
        path.addEllipse(QtCore.QPointF(0, 0), inner_radius, inner_radius)
        painter.drawPath(path)

        # 绘制中心孔（透明）
        painter.setBrush(QtGui.QBrush(QtCore.Qt.transparent))
        painter.setPen(painter.pen())
        hole_radius = inner_radius * 0.4  # 调整中心孔大小
        painter.drawEllipse(QtCore.QPointF(0, 0), hole_radius, hole_radius)

        painter.restore()
    
    @staticmethod
    def _draw_log_icon(painter: QtGui.QPainter, rect: QtCore.QRect):
        """绘制日志图标（现代化文档）"""
        # 绘制文档主体（圆角矩形）
        margin = rect.width() // 8
        doc_rect = QtCore.QRect(rect.left() + margin, rect.top(),
                               int(rect.width() * 0.75), rect.height())

        # 使用渐变填充
        gradient = QtGui.QLinearGradient(doc_rect.topLeft(), doc_rect.bottomRight())
        gradient.setColorAt(0, painter.pen().color().lighter(110))
        gradient.setColorAt(1, painter.pen().color())
        painter.setBrush(QtGui.QBrush(gradient))

        # 绘制圆角文档
        painter.drawRoundedRect(doc_rect, 2, 2)

        # 绘制文档折角（更精细）
        corner_size = rect.width() // 5
        corner_points = [
            QtCore.QPoint(doc_rect.right() - corner_size, doc_rect.top()),
            QtCore.QPoint(doc_rect.right(), doc_rect.top() + corner_size),
            QtCore.QPoint(doc_rect.right() - corner_size, doc_rect.top() + corner_size)
        ]
        painter.setBrush(QtGui.QBrush(painter.pen().color().darker(120)))
        painter.drawPolygon(corner_points)

        # 绘制文本行（更现代的样式）
        painter.setBrush(QtGui.QBrush(painter.pen().color()))
        line_height = rect.height() // 7
        line_width = int(rect.width() * 0.5)

        for i in range(3):
            y = rect.top() + (i + 2.5) * line_height
            line_rect = QtCore.QRect(rect.left() + rect.width() // 6, int(y),
                                   line_width - i * (line_width // 6), 1)
            painter.drawRoundedRect(line_rect, 0.5, 0.5)
    
    @staticmethod
    def _draw_quit_icon(painter: QtGui.QPainter, rect: QtCore.QRect):
        """绘制退出图标（X）"""
        # 绘制X
        painter.drawLine(rect.topLeft(), rect.bottomRight())
        painter.drawLine(rect.topRight(), rect.bottomLeft())
    
    @staticmethod
    def _draw_status_icon(painter: QtGui.QPainter, rect: QtCore.QRect):
        """绘制状态图标（信息圆圈）"""
        # 绘制圆圈
        painter.drawEllipse(rect)
        
        # 绘制信息符号 "i"
        center = rect.center()
        dot_radius = rect.width() // 12
        
        # 上方的点
        dot_rect = QtCore.QRect(center.x() - dot_radius, 
                               center.y() - rect.height() // 3,
                               dot_radius * 2, dot_radius * 2)
        painter.drawEllipse(dot_rect)
        
        # 下方的竖线
        line_rect = QtCore.QRect(center.x() - dot_radius // 2,
                                center.y() - rect.height() // 6,
                                dot_radius, rect.height() // 3)
        painter.drawRect(line_rect)
    
    @staticmethod
    def _draw_screen_icon(painter: QtGui.QPainter, rect: QtCore.QRect):
        """绘制屏幕图标（显示器）"""
        # 绘制显示器屏幕
        screen_rect = QtCore.QRect(rect.left(), rect.top(),
                                  rect.width(), int(rect.height() * 0.7))
        painter.drawRect(screen_rect)
        
        # 绘制底座
        base_width = rect.width() // 3
        base_rect = QtCore.QRect(rect.center().x() - base_width // 2,
                                screen_rect.bottom(),
                                base_width, rect.height() - screen_rect.height())
        painter.drawRect(base_rect)
    
    @staticmethod
    def _draw_check_icon(painter: QtGui.QPainter, rect: QtCore.QRect):
        """绘制勾选图标（✓）"""
        # 绘制勾选标记
        points = [
            QtCore.QPoint(rect.left() + rect.width() // 4, rect.center().y()),
            QtCore.QPoint(rect.center().x(), rect.bottom() - rect.height() // 4),
            QtCore.QPoint(rect.right() - rect.width() // 6, rect.top() + rect.height() // 4)
        ]
        
        # 使用较粗的线条绘制勾选
        pen = painter.pen()
        pen.setWidth(max(2, rect.width() // 8))
        painter.setPen(pen)
        
        painter.drawLine(points[0], points[1])
        painter.drawLine(points[1], points[2])


def create_menu_icon(icon_type: str, size: int = 16, color: str = "#E6E6E6") -> QtGui.QIcon:
    """便捷函数：创建菜单图标"""
    return MenuIconManager.create_icon(icon_type, size, color)

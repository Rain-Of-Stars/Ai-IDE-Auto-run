# -*- coding: utf-8 -*-
"""
UI优化器 - 提供高效的UI更新机制，减少卡顿
主要优化策略：
1. 批量UI更新机制
2. 智能状态缓存
3. 节流更新控制
4. 资源管理优化
"""
from __future__ import annotations
import time
from typing import Dict, Any, Optional
from PySide6 import QtCore, QtWidgets, QtGui


class UIUpdateBatcher(QtCore.QObject):
    """UI更新批处理器 - 减少频繁的UI更新操作"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pending_updates = {}
        self._update_timer = QtCore.QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._apply_pending_updates)
        self._batch_delay = 100  # 增加到100ms批量延迟以降低资源占用

        # 状态缓存
        self._cached_states = {}

        # 限制缓存大小以控制内存使用
        self._max_cache_size = 50
        
    def schedule_update(self, widget_id: str, update_data: Dict[str, Any]):
        """调度UI更新"""
        # 检查是否需要更新
        if self._is_update_needed(widget_id, update_data):
            self._pending_updates[widget_id] = update_data

            # 清理缓存以控制内存使用
            self._cleanup_cache_if_needed()

            # 启动批量更新定时器
            if not self._update_timer.isActive():
                self._update_timer.start(self._batch_delay)
    
    def _is_update_needed(self, widget_id: str, update_data: Dict[str, Any]) -> bool:
        """检查是否需要更新（避免重复更新）"""
        cached = self._cached_states.get(widget_id)
        if cached is None:
            return True
        
        # 比较关键字段
        for key, value in update_data.items():
            if cached.get(key) != value:
                return True
        return False
    
    def _apply_pending_updates(self):
        """应用待处理的UI更新"""
        if not self._pending_updates:
            return
        
        # 批量应用更新
        for widget_id, update_data in self._pending_updates.items():
            try:
                self._apply_single_update(widget_id, update_data)
                # 更新缓存
                self._cached_states[widget_id] = update_data.copy()
            except Exception as e:
                print(f"UI更新失败 {widget_id}: {e}")
        
        # 清空待处理队列
        self._pending_updates.clear()
    
    def _apply_single_update(self, widget_id: str, update_data: Dict[str, Any]):
        """应用单个UI更新 - 子类需要重写此方法"""
        pass

    def _cleanup_cache_if_needed(self):
        """清理缓存以控制内存使用"""
        if len(self._cached_states) > self._max_cache_size:
            # 移除最旧的一半缓存项
            items_to_remove = len(self._cached_states) // 2
            keys_to_remove = list(self._cached_states.keys())[:items_to_remove]
            for key in keys_to_remove:
                del self._cached_states[key]


class TrayMenuOptimizer(UIUpdateBatcher):
    """托盘菜单优化器"""
    
    def __init__(self, tray_icon, parent=None):
        super().__init__(parent)
        self.tray_icon = tray_icon
        self._last_tooltip_update = 0.0
        self._tooltip_update_interval = 2.0  # 2秒更新间隔
    
    def update_status(self, text: str):
        """优化的状态更新"""
        raw = text or ""
        parts = [p.strip() for p in raw.split('|')]

        # 解析状态信息
        line1 = parts[0] if parts else raw
        is_running = any(keyword in line1 for keyword in ["运行", "扫描", "检测", "匹配"])
        new_status = f"状态: {line1}"

        # 解析后端信息
        backend = "-"
        for p in parts:
            if p.startswith("后端:"):
                backend = p.split("后端:", 1)[1].strip()
                break
        new_backend = f"后端: {backend}"

        # 解析详细信息
        detail = ""
        has_multi = any("多屏轮询" in p for p in parts)
        cur_screen = None
        score_text = None
        for p in parts:
            if p.startswith("当前屏幕:"):
                cur_screen = p
            if p.startswith("匹配:") or p.startswith("上次匹配:"):
                score_text = p.replace("上次匹配:", "匹配:").strip()
        if has_multi and (cur_screen or score_text):
            detail = " | ".join(filter(None, [cur_screen, score_text]))
        else:
            for p in parts[::-1]:
                if p.startswith("上次匹配:") or p.startswith("匹配:"):
                    detail = p
                    break

        # 调度批量更新
        self.schedule_update('tray_menu', {
            'status': new_status,
            'is_running': is_running,
            'backend': new_backend,
            'detail': detail,
            'tooltip_update': True
        })
    
    def _apply_single_update(self, widget_id: str, update_data: Dict[str, Any]):
        """应用托盘菜单更新"""
        if widget_id == 'tray_menu':
            # 更新状态
            if 'status' in update_data:
                self.tray_icon._set_status_with_color(
                    update_data['status'], 
                    is_running=update_data.get('is_running', False)
                )
            
            # 更新后端
            if 'backend' in update_data:
                self.tray_icon.act_backend.setText(update_data['backend'])
            
            # 更新详细信息
            if 'detail' in update_data:
                self.tray_icon.act_detail.setText(update_data['detail'])
            
            # 更新tooltip（带节流）
            if update_data.get('tooltip_update'):
                self._update_tooltip_throttled()
    
    def _update_tooltip_throttled(self):
        """节流的tooltip更新"""
        now = time.monotonic()
        if now - self._last_tooltip_update < self._tooltip_update_interval:
            return
        
        self._last_tooltip_update = now
        tooltip = "AI-IDE-Auto-Run - " + "\n".join(filter(None, [
            self.tray_icon.act_status.text(),
            self.tray_icon.act_backend.text(),
            self.tray_icon.act_detail.text()
        ]))
        self.tray_icon.setToolTip(tooltip)


class PerformanceThrottler:
    """性能节流器 - 控制更新频率"""
    
    def __init__(self):
        self._last_updates = {}
        self._default_interval = 1.0  # 默认1秒间隔
    
    def should_update(self, key: str, interval: Optional[float] = None) -> bool:
        """检查是否应该更新"""
        now = time.monotonic()
        last_update = self._last_updates.get(key, 0)
        update_interval = interval or self._default_interval
        
        if now - last_update >= update_interval:
            self._last_updates[key] = now
            return True
        return False
    
    def force_update(self, key: str):
        """强制更新（重置时间戳）"""
        self._last_updates[key] = 0


class ResourceManager:
    """资源管理器 - 优化内存使用
    注意：避免在没有QApplication实例时启动QTimer，否则会出现
    “QObject::startTimer: Timers can only be used with threads started with QThread” 警告。
    因此这里采用惰性启动定时器的策略。
    """

    def __init__(self):
        self._cached_resources = {}
        self._cleanup_timer: QtCore.QTimer | None = None
        self._maybe_start_timer()

    def _maybe_start_timer(self):
        """若当前已有Qt应用实例，则创建并启动清理定时器。"""
        try:
            app = QtCore.QCoreApplication.instance()
            if app is None:
                return  # 尚未创建QApplication，稍后再启动
            if self._cleanup_timer is None:
                self._cleanup_timer = QtCore.QTimer()
                self._cleanup_timer.timeout.connect(self._cleanup_resources)
                self._cleanup_timer.start(30000)  # 30秒清理一次
        except Exception:
            # 静默忽略，避免在早期导入阶段影响启动
            self._cleanup_timer = None

    def get_cached_resource(self, key: str, factory_func):
        """获取缓存的资源"""
        self._maybe_start_timer()
        if key not in self._cached_resources:
            self._cached_resources[key] = factory_func()
        return self._cached_resources[key]

    def _cleanup_resources(self):
        """清理未使用的资源"""
        # 这里可以添加资源清理逻辑
        pass

    def clear_cache(self):
        """清空缓存"""
        self._cached_resources.clear()
        self._maybe_start_timer()


# 全局实例
_performance_throttler = PerformanceThrottler()
_resource_manager = ResourceManager()


def get_performance_throttler() -> PerformanceThrottler:
    """获取性能节流器实例"""
    return _performance_throttler


def get_resource_manager() -> ResourceManager:
    """获取资源管理器实例"""
    return _resource_manager

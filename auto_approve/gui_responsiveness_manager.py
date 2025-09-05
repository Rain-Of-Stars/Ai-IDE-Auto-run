# -*- coding: utf-8 -*-
"""
GUI响应性管理器
确保GUI始终保持响应，防止任何操作阻塞用户界面
"""
from __future__ import annotations
import time
import threading
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QObject, Signal, QTimer, QElapsedTimer

from auto_approve.logger_manager import get_logger


@dataclass
class UIUpdateRequest:
    """UI更新请求"""
    widget_id: str
    update_type: str
    data: Dict[str, Any]
    priority: int = 0  # 优先级，数字越大优先级越高
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class GuiResponsivenessManager(QObject):
    """GUI响应性管理器
    
    主要功能：
    1. 批量处理UI更新，避免频繁刷新
    2. 监控GUI响应时间
    3. 自动调节更新频率
    4. 提供UI操作的异步包装
    """
    
    # 信号
    responsiveness_warning = Signal(float)  # 响应时间警告
    update_batch_processed = Signal(int)    # 批处理完成
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        
        # 更新队列和批处理
        self._update_queue: List[UIUpdateRequest] = []
        self._update_handlers: Dict[str, Callable] = {}
        self._queue_lock = threading.Lock()
        
        # 批处理定时器
        self._batch_timer = QTimer()
        self._batch_timer.setSingleShot(True)
        self._batch_timer.timeout.connect(self._process_update_batch)
        
        # 响应性监控
        self._response_timer = QElapsedTimer()
        self._last_response_check = 0.0
        self._response_threshold_ms = 100  # 100ms响应阈值
        
        # 自适应配置
        self._batch_delay_ms = 50  # 初始批处理延迟
        self._max_batch_delay_ms = 200  # 最大批处理延迟
        self._min_batch_delay_ms = 16   # 最小批处理延迟（约60FPS）
        
        # 性能统计
        self._stats = {
            'total_updates': 0,
            'batches_processed': 0,
            'avg_batch_size': 0.0,
            'avg_response_time': 0.0,
            'slow_responses': 0
        }
        
        # 启动响应性监控
        self._start_responsiveness_monitoring()
    
    def register_update_handler(self, update_type: str, handler: Callable[[UIUpdateRequest], None]):
        """注册UI更新处理器
        
        Args:
            update_type: 更新类型（如 'tooltip', 'status', 'menu'）
            handler: 处理函数，接收UIUpdateRequest参数
        """
        self._update_handlers[update_type] = handler
        self.logger.debug(f"注册UI更新处理器: {update_type}")
    
    def schedule_ui_update(self, widget_id: str, update_type: str, 
                          data: Dict[str, Any], priority: int = 0):
        """调度UI更新
        
        Args:
            widget_id: 控件ID
            update_type: 更新类型
            data: 更新数据
            priority: 优先级（0-10，数字越大优先级越高）
        """
        request = UIUpdateRequest(
            widget_id=widget_id,
            update_type=update_type,
            data=data,
            priority=priority
        )
        
        with self._queue_lock:
            # 检查是否有相同控件的待处理更新，如果有则替换
            existing_index = -1
            for i, existing in enumerate(self._update_queue):
                if existing.widget_id == widget_id and existing.update_type == update_type:
                    existing_index = i
                    break
            
            if existing_index >= 0:
                # 替换现有更新
                self._update_queue[existing_index] = request
            else:
                # 添加新更新
                self._update_queue.append(request)
            
            self._stats['total_updates'] += 1
        
        # 启动批处理定时器
        if not self._batch_timer.isActive():
            self._batch_timer.start(self._batch_delay_ms)
    
    def _process_update_batch(self):
        """处理更新批次"""
        start_time = QElapsedTimer()
        start_time.start()
        
        with self._queue_lock:
            if not self._update_queue:
                return
            
            # 按优先级排序
            self._update_queue.sort(key=lambda x: x.priority, reverse=True)
            
            # 复制队列并清空
            batch = self._update_queue.copy()
            self._update_queue.clear()
        
        # 处理批次
        processed_count = 0
        for request in batch:
            try:
                handler = self._update_handlers.get(request.update_type)
                if handler:
                    handler(request)
                    processed_count += 1
                else:
                    self.logger.warning(f"未找到更新处理器: {request.update_type}")
            except Exception as e:
                self.logger.error(f"处理UI更新失败 {request.widget_id}: {e}")
        
        # 更新统计
        processing_time = start_time.elapsed()
        self._stats['batches_processed'] += 1
        self._stats['avg_batch_size'] = (
            (self._stats['avg_batch_size'] * (self._stats['batches_processed'] - 1) + len(batch)) 
            / self._stats['batches_processed']
        )
        
        # 自适应调整批处理延迟
        self._adjust_batch_delay(processing_time)
        
        # 发送完成信号
        self.update_batch_processed.emit(processed_count)
        
        self.logger.debug(f"处理UI更新批次: {processed_count}个更新, 耗时: {processing_time}ms")
    
    def _adjust_batch_delay(self, processing_time_ms: float):
        """自适应调整批处理延迟"""
        if processing_time_ms > self._response_threshold_ms:
            # 处理时间过长，增加延迟
            self._batch_delay_ms = min(
                self._batch_delay_ms + 10,
                self._max_batch_delay_ms
            )
        elif processing_time_ms < self._response_threshold_ms / 2:
            # 处理很快，可以减少延迟
            self._batch_delay_ms = max(
                self._batch_delay_ms - 5,
                self._min_batch_delay_ms
            )
    
    def _start_responsiveness_monitoring(self):
        """启动响应性监控"""
        self._response_timer.start()
        
        # 每秒检查一次响应性
        monitor_timer = QTimer()
        monitor_timer.timeout.connect(self._check_responsiveness)
        monitor_timer.start(1000)  # 1秒间隔
    
    def _check_responsiveness(self):
        """检查GUI响应性"""
        current_time = time.time()
        
        # 检查是否有长时间未响应
        if current_time - self._last_response_check > 2.0:  # 2秒未检查
            response_time = current_time - self._last_response_check
            self._stats['slow_responses'] += 1
            self.responsiveness_warning.emit(response_time)
            self.logger.warning(f"GUI响应缓慢: {response_time:.2f}秒")
        
        self._last_response_check = current_time
    
    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return self._stats.copy()
    
    def force_process_updates(self):
        """强制处理所有待处理的更新"""
        if self._batch_timer.isActive():
            self._batch_timer.stop()
        self._process_update_batch()
    
    def clear_pending_updates(self):
        """清空待处理的更新"""
        with self._queue_lock:
            cleared_count = len(self._update_queue)
            self._update_queue.clear()
        
        if cleared_count > 0:
            self.logger.info(f"清空了 {cleared_count} 个待处理的UI更新")
    
    def set_response_threshold(self, threshold_ms: float):
        """设置响应时间阈值"""
        self._response_threshold_ms = threshold_ms
        self.logger.info(f"响应时间阈值设置为: {threshold_ms}ms")


# 全局实例
_global_gui_manager: Optional[GuiResponsivenessManager] = None


def get_gui_responsiveness_manager() -> GuiResponsivenessManager:
    """获取全局GUI响应性管理器"""
    global _global_gui_manager
    if _global_gui_manager is None:
        _global_gui_manager = GuiResponsivenessManager()
    return _global_gui_manager


def schedule_ui_update(widget_id: str, update_type: str, 
                      data: Dict[str, Any], priority: int = 0):
    """便捷函数：调度UI更新"""
    manager = get_gui_responsiveness_manager()
    manager.schedule_ui_update(widget_id, update_type, data, priority)


def register_ui_handler(update_type: str, handler: Callable[[UIUpdateRequest], None]):
    """便捷函数：注册UI更新处理器"""
    manager = get_gui_responsiveness_manager()
    manager.register_update_handler(update_type, handler)

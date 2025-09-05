# -*- coding: utf-8 -*-
"""
GUI性能监控器
实时监控GUI响应性，检测卡顿和性能问题
"""
from __future__ import annotations
import time
import threading
import psutil
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QObject, Signal, QTimer, QElapsedTimer

from auto_approve.logger_manager import get_logger


@dataclass
class GuiPerformanceMetrics:
    """GUI性能指标"""
    timestamp: float
    main_thread_cpu_percent: float
    memory_usage_mb: float
    event_loop_latency_ms: float
    ui_update_count: int
    pending_events: int
    response_time_ms: float
    is_responsive: bool


class GuiPerformanceMonitor(QObject):
    """GUI性能监控器
    
    监控内容：
    1. 主线程CPU使用率
    2. 内存使用情况
    3. 事件循环延迟
    4. UI更新频率
    5. 响应时间
    """
    
    # 信号
    performance_alert = Signal(str, float)  # 性能警告：类型，数值
    metrics_updated = Signal(object)        # 性能指标更新
    responsiveness_changed = Signal(bool)   # 响应性状态变化
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        
        # 监控配置
        self._monitor_interval_ms = 1000  # 1秒监控间隔
        self._response_threshold_ms = 200  # 200ms响应阈值
        self._cpu_threshold_percent = 80   # 80% CPU阈值
        self._memory_threshold_mb = 500    # 500MB内存阈值
        
        # 监控状态
        self._monitoring = False
        self._last_responsive = True
        self._metrics_history: List[GuiPerformanceMetrics] = []
        self._max_history = 60  # 保留60秒历史
        
        # 性能计时器
        self._response_timer = QElapsedTimer()
        self._last_event_time = 0.0
        
        # UI更新统计
        self._ui_update_count = 0
        self._last_ui_count_reset = time.time()
        
        # 监控定时器
        self._monitor_timer = QTimer()
        self._monitor_timer.timeout.connect(self._collect_metrics)
        self._monitor_timer.setInterval(self._monitor_interval_ms)
        
        # 响应性测试定时器
        self._response_test_timer = QTimer()
        self._response_test_timer.timeout.connect(self._test_responsiveness)
        self._response_test_timer.setInterval(500)  # 500ms测试间隔
        
        # 进程信息
        self._process = psutil.Process()
        
        self.logger.info("GUI性能监控器已初始化")
    
    def start_monitoring(self):
        """开始监控"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._response_timer.start()
        self._last_event_time = time.time()
        
        # 启动监控定时器
        self._monitor_timer.start()
        self._response_test_timer.start()
        
        self.logger.info("GUI性能监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        if not self._monitoring:
            return
        
        self._monitoring = False
        self._monitor_timer.stop()
        self._response_test_timer.stop()
        
        self.logger.info("GUI性能监控已停止")
    
    def record_ui_update(self):
        """记录UI更新"""
        self._ui_update_count += 1
        self._last_event_time = time.time()
    
    def _collect_metrics(self):
        """收集性能指标"""
        if not self._monitoring:
            return
        
        try:
            current_time = time.time()
            
            # 收集系统指标
            cpu_percent = self._process.cpu_percent()
            memory_mb = self._process.memory_info().rss / 1024 / 1024
            
            # 计算事件循环延迟
            event_loop_latency = self._calculate_event_loop_latency()
            
            # 计算UI更新频率
            time_since_reset = current_time - self._last_ui_count_reset
            ui_update_rate = self._ui_update_count / max(time_since_reset, 1.0)
            
            # 重置UI更新计数
            if time_since_reset >= 1.0:
                self._ui_update_count = 0
                self._last_ui_count_reset = current_time
            
            # 获取待处理事件数量
            pending_events = self._get_pending_events_count()
            
            # 计算响应时间
            response_time = (current_time - self._last_event_time) * 1000
            is_responsive = response_time < self._response_threshold_ms
            
            # 创建性能指标
            metrics = GuiPerformanceMetrics(
                timestamp=current_time,
                main_thread_cpu_percent=cpu_percent,
                memory_usage_mb=memory_mb,
                event_loop_latency_ms=event_loop_latency,
                ui_update_count=int(ui_update_rate),
                pending_events=pending_events,
                response_time_ms=response_time,
                is_responsive=is_responsive
            )
            
            # 添加到历史记录
            self._metrics_history.append(metrics)
            if len(self._metrics_history) > self._max_history:
                self._metrics_history.pop(0)
            
            # 检查性能警告
            self._check_performance_alerts(metrics)
            
            # 发送更新信号
            self.metrics_updated.emit(metrics)
            
        except Exception as e:
            self.logger.error(f"收集性能指标失败: {e}")
    
    def _calculate_event_loop_latency(self) -> float:
        """计算事件循环延迟"""
        # 简单的延迟估算：基于定时器精度
        expected_interval = self._monitor_interval_ms
        actual_interval = self._response_timer.elapsed()
        self._response_timer.restart()
        
        latency = abs(actual_interval - expected_interval)
        return min(latency, 1000)  # 限制最大延迟为1秒
    
    def _get_pending_events_count(self) -> int:
        """获取待处理事件数量"""
        try:
            # 这是一个估算，Qt没有直接的API获取待处理事件数
            app = QtWidgets.QApplication.instance()
            if app:
                # 通过处理事件来估算
                processed = 0
                while app.hasPendingEvents() and processed < 10:
                    app.processEvents(QtCore.QEventLoop.AllEvents, 0)
                    processed += 1
                return processed
            return 0
        except:
            return 0
    
    def _test_responsiveness(self):
        """测试GUI响应性"""
        if not self._monitoring:
            return
        
        current_time = time.time()
        response_time = (current_time - self._last_event_time) * 1000
        is_responsive = response_time < self._response_threshold_ms
        
        # 检查响应性状态变化
        if is_responsive != self._last_responsive:
            self._last_responsive = is_responsive
            self.responsiveness_changed.emit(is_responsive)
            
            if not is_responsive:
                self.logger.warning(f"GUI响应性下降: {response_time:.1f}ms")
            else:
                self.logger.info("GUI响应性恢复")
    
    def _check_performance_alerts(self, metrics: GuiPerformanceMetrics):
        """检查性能警告"""
        # CPU使用率警告
        if metrics.main_thread_cpu_percent > self._cpu_threshold_percent:
            self.performance_alert.emit("high_cpu", metrics.main_thread_cpu_percent)
        
        # 内存使用警告
        if metrics.memory_usage_mb > self._memory_threshold_mb:
            self.performance_alert.emit("high_memory", metrics.memory_usage_mb)
        
        # 响应时间警告
        if metrics.response_time_ms > self._response_threshold_ms:
            self.performance_alert.emit("slow_response", metrics.response_time_ms)
        
        # 事件循环延迟警告
        if metrics.event_loop_latency_ms > 100:
            self.performance_alert.emit("high_latency", metrics.event_loop_latency_ms)
    
    def get_current_metrics(self) -> Optional[GuiPerformanceMetrics]:
        """获取当前性能指标"""
        return self._metrics_history[-1] if self._metrics_history else None
    
    def get_metrics_history(self) -> List[GuiPerformanceMetrics]:
        """获取性能指标历史"""
        return self._metrics_history.copy()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        if not self._metrics_history:
            return {}
        
        recent_metrics = self._metrics_history[-10:]  # 最近10秒
        
        return {
            'avg_cpu_percent': sum(m.main_thread_cpu_percent for m in recent_metrics) / len(recent_metrics),
            'avg_memory_mb': sum(m.memory_usage_mb for m in recent_metrics) / len(recent_metrics),
            'avg_response_time_ms': sum(m.response_time_ms for m in recent_metrics) / len(recent_metrics),
            'responsive_ratio': sum(1 for m in recent_metrics if m.is_responsive) / len(recent_metrics),
            'total_samples': len(self._metrics_history),
            'monitoring_duration_s': len(self._metrics_history) * (self._monitor_interval_ms / 1000)
        }
    
    def set_thresholds(self, response_ms: int = None, cpu_percent: float = None, 
                      memory_mb: float = None):
        """设置性能阈值"""
        if response_ms is not None:
            self._response_threshold_ms = response_ms
        if cpu_percent is not None:
            self._cpu_threshold_percent = cpu_percent
        if memory_mb is not None:
            self._memory_threshold_mb = memory_mb
        
        self.logger.info(f"性能阈值已更新: 响应时间={self._response_threshold_ms}ms, "
                        f"CPU={self._cpu_threshold_percent}%, 内存={self._memory_threshold_mb}MB")


# 全局实例
_global_gui_monitor: Optional[GuiPerformanceMonitor] = None


def get_gui_performance_monitor() -> GuiPerformanceMonitor:
    """获取全局GUI性能监控器"""
    global _global_gui_monitor
    if _global_gui_monitor is None:
        _global_gui_monitor = GuiPerformanceMonitor()
    return _global_gui_monitor


def start_gui_monitoring():
    """启动GUI性能监控"""
    monitor = get_gui_performance_monitor()
    monitor.start_monitoring()


def stop_gui_monitoring():
    """停止GUI性能监控"""
    monitor = get_gui_performance_monitor()
    monitor.stop_monitoring()


def record_ui_update():
    """记录UI更新（便捷函数）"""
    monitor = get_gui_performance_monitor()
    monitor.record_ui_update()

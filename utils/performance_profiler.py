# -*- coding: utf-8 -*-
"""
性能分析器 - QElapsedTimer性能埋点

提供高精度的性能计时和分析功能：
- 启动时间监控
- 首次绘制时间
- 关键操作时延
- 性能热点分析
"""

import time
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import json
import os

from PySide6 import QtCore
from PySide6.QtCore import QElapsedTimer, QObject, Signal

from auto_approve.logger_manager import get_logger


@dataclass
class PerformanceRecord:
    """性能记录"""
    name: str
    start_time: float
    end_time: float
    duration_ms: float
    thread_id: int
    thread_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceStats:
    """性能统计"""
    operation_name: str
    total_calls: int
    total_duration_ms: float
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float


class PerformanceProfiler(QObject):
    """性能分析器"""
    
    # 性能记录信号
    performance_recorded = Signal(object)  # PerformanceRecord
    # 性能警告信号
    performance_warning = Signal(str, float)  # operation_name, duration_ms
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger()
        
        # 性能记录存储
        self.records: List[PerformanceRecord] = []
        self.max_records = 10000  # 最多保留10000条记录
        
        # 活跃计时器
        self.active_timers: Dict[str, QElapsedTimer] = {}
        self.timer_metadata: Dict[str, Dict[str, Any]] = {}
        
        # 性能阈值
        self.warning_thresholds = {
            'startup': 3000,      # 启动超过3秒
            'ui_render': 16,      # UI渲染超过16ms (60fps)
            'file_io': 100,       # 文件IO超过100ms
            'network': 5000,      # 网络请求超过5秒
            'cpu_task': 1000,     # CPU任务超过1秒
            'default': 500        # 默认阈值500ms
        }
        
        # 线程安全锁
        self._lock = threading.Lock()
        
        # 启动时间记录
        self.app_start_timer = QElapsedTimer()
        self.app_start_timer.start()
        
        # 关键里程碑
        self.milestones: Dict[str, float] = {}
        
        self.logger.info("性能分析器已初始化")
    
    def start_timer(self, operation_name: str, metadata: Dict[str, Any] = None) -> str:
        """开始计时
        
        Args:
            operation_name: 操作名称
            metadata: 附加元数据
        
        Returns:
            str: 计时器ID
        """
        timer_id = f"{operation_name}_{int(time.time() * 1000000)}"
        
        with self._lock:
            timer = QElapsedTimer()
            timer.start()
            
            self.active_timers[timer_id] = timer
            self.timer_metadata[timer_id] = {
                'operation_name': operation_name,
                'metadata': metadata or {},
                'thread_id': threading.get_ident(),
                'thread_name': threading.current_thread().name
            }
        
        return timer_id
    
    def end_timer(self, timer_id: str) -> Optional[PerformanceRecord]:
        """结束计时
        
        Args:
            timer_id: 计时器ID
        
        Returns:
            PerformanceRecord: 性能记录
        """
        with self._lock:
            if timer_id not in self.active_timers:
                self.logger.warning(f"计时器不存在: {timer_id}")
                return None
            
            timer = self.active_timers.pop(timer_id)
            timer_meta = self.timer_metadata.pop(timer_id)
            
            duration_ms = timer.elapsed()
            end_time = time.time()
            start_time = end_time - (duration_ms / 1000.0)
            
            record = PerformanceRecord(
                name=timer_meta['operation_name'],
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                thread_id=timer_meta['thread_id'],
                thread_name=timer_meta['thread_name'],
                metadata=timer_meta['metadata']
            )
            
            # 添加记录
            self._add_record(record)
            
            # 检查性能警告
            self._check_performance_warning(record)
            
            return record
    
    def measure(self, operation_name: str, category: str = 'default', 
               metadata: Dict[str, Any] = None):
        """性能测量装饰器
        
        Args:
            operation_name: 操作名称
            category: 操作类别，用于确定警告阈值
            metadata: 附加元数据
        """
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs):
                timer_id = self.start_timer(operation_name, metadata)
                
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    record = self.end_timer(timer_id)
                    if record:
                        # 检查类别特定的阈值
                        threshold = self.warning_thresholds.get(category, 
                                                              self.warning_thresholds['default'])
                        if record.duration_ms > threshold:
                            self.performance_warning.emit(operation_name, record.duration_ms)
            
            return wrapper
        return decorator
    
    def record_milestone(self, milestone_name: str):
        """记录关键里程碑
        
        Args:
            milestone_name: 里程碑名称
        """
        elapsed_ms = self.app_start_timer.elapsed()
        self.milestones[milestone_name] = elapsed_ms
        
        self.logger.info(f"里程碑 {milestone_name}: {elapsed_ms}ms")
        
        # 发送性能记录信号
        record = PerformanceRecord(
            name=f"milestone_{milestone_name}",
            start_time=time.time() - (elapsed_ms / 1000.0),
            end_time=time.time(),
            duration_ms=elapsed_ms,
            thread_id=threading.get_ident(),
            thread_name=threading.current_thread().name,
            metadata={'milestone': True, 'from_app_start': True}
        )
        
        self._add_record(record)
    
    def _add_record(self, record: PerformanceRecord):
        """添加性能记录"""
        self.records.append(record)
        
        # 保持记录数量在限制内
        if len(self.records) > self.max_records:
            self.records = self.records[-self.max_records:]
        
        # 发送信号
        self.performance_recorded.emit(record)
    
    def _check_performance_warning(self, record: PerformanceRecord):
        """检查性能警告"""
        # 根据操作名称推断类别
        category = 'default'
        name_lower = record.name.lower()
        
        if 'startup' in name_lower or 'init' in name_lower:
            category = 'startup'
        elif 'render' in name_lower or 'paint' in name_lower or 'draw' in name_lower:
            category = 'ui_render'
        elif 'file' in name_lower or 'read' in name_lower or 'write' in name_lower:
            category = 'file_io'
        elif 'http' in name_lower or 'network' in name_lower or 'request' in name_lower:
            category = 'network'
        elif 'cpu' in name_lower or 'compute' in name_lower or 'process' in name_lower:
            category = 'cpu_task'
        
        threshold = self.warning_thresholds.get(category, self.warning_thresholds['default'])
        
        if record.duration_ms > threshold:
            self.logger.warning(
                f"性能警告: {record.name} 耗时 {record.duration_ms}ms "
                f"(阈值: {threshold}ms, 线程: {record.thread_name})"
            )
            self.performance_warning.emit(record.name, record.duration_ms)
    
    def get_stats(self, operation_name: str = None) -> List[PerformanceStats]:
        """获取性能统计
        
        Args:
            operation_name: 特定操作名称，None表示所有操作
        
        Returns:
            List[PerformanceStats]: 性能统计列表
        """
        # 按操作名称分组
        grouped_records = defaultdict(list)
        
        for record in self.records:
            if operation_name is None or record.name == operation_name:
                grouped_records[record.name].append(record.duration_ms)
        
        stats_list = []
        
        for op_name, durations in grouped_records.items():
            if not durations:
                continue
            
            durations.sort()
            total_calls = len(durations)
            total_duration = sum(durations)
            
            # 计算百分位数
            p95_index = int(total_calls * 0.95)
            p99_index = int(total_calls * 0.99)
            
            stats = PerformanceStats(
                operation_name=op_name,
                total_calls=total_calls,
                total_duration_ms=total_duration,
                avg_duration_ms=total_duration / total_calls,
                min_duration_ms=min(durations),
                max_duration_ms=max(durations),
                p95_duration_ms=durations[p95_index] if p95_index < total_calls else durations[-1],
                p99_duration_ms=durations[p99_index] if p99_index < total_calls else durations[-1]
            )
            
            stats_list.append(stats)
        
        # 按平均耗时排序
        stats_list.sort(key=lambda x: x.avg_duration_ms, reverse=True)
        
        return stats_list
    
    def get_milestones(self) -> Dict[str, float]:
        """获取里程碑记录"""
        return self.milestones.copy()
    
    def export_report(self, file_path: str):
        """导出性能报告
        
        Args:
            file_path: 报告文件路径
        """
        try:
            stats = self.get_stats()
            
            report = {
                'timestamp': time.time(),
                'total_records': len(self.records),
                'milestones': self.milestones,
                'performance_stats': [
                    {
                        'operation_name': stat.operation_name,
                        'total_calls': stat.total_calls,
                        'avg_duration_ms': stat.avg_duration_ms,
                        'max_duration_ms': stat.max_duration_ms,
                        'p95_duration_ms': stat.p95_duration_ms,
                        'p99_duration_ms': stat.p99_duration_ms
                    }
                    for stat in stats
                ],
                'warning_thresholds': self.warning_thresholds,
                'top_slow_operations': [
                    {
                        'name': stat.operation_name,
                        'avg_duration_ms': stat.avg_duration_ms
                    }
                    for stat in stats[:10]  # 前10个最慢的操作
                ]
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"性能报告已导出: {file_path}")
            
        except Exception as e:
            self.logger.error(f"导出性能报告失败: {e}")
    
    def clear_records(self):
        """清空性能记录"""
        with self._lock:
            self.records.clear()
            self.milestones.clear()
            self.app_start_timer.restart()
        
        self.logger.info("性能记录已清空")


# 全局性能分析器实例
_global_profiler: Optional[PerformanceProfiler] = None


def get_global_profiler() -> PerformanceProfiler:
    """获取全局性能分析器实例"""
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = PerformanceProfiler()
    return _global_profiler


def measure_performance(operation_name: str, category: str = 'default', 
                       metadata: Dict[str, Any] = None):
    """便捷的性能测量装饰器"""
    profiler = get_global_profiler()
    return profiler.measure(operation_name, category, metadata)


def record_milestone(milestone_name: str):
    """记录里程碑"""
    profiler = get_global_profiler()
    profiler.record_milestone(milestone_name)


def export_performance_report(file_path: str = None):
    """导出性能报告"""
    if file_path is None:
        file_path = f"performance_report_{int(time.time())}.json"
    
    profiler = get_global_profiler()
    profiler.export_report(file_path)
    return file_path

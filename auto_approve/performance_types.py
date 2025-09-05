# -*- coding: utf-8 -*-
"""
统一的性能数据类型定义

集中定义所有性能监控相关的数据结构，避免重复定义和冲突
"""

from dataclasses import dataclass, field
import time
from typing import Dict, Any, Optional


@dataclass
class PerformanceMetrics:
    """统一的性能指标数据类
    
    整合了原有的多个PerformanceMetrics定义，提供完整的性能监控数据结构
    """
    # 基础时间戳
    timestamp: float = field(default_factory=time.time)
    
    # CPU和内存指标
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    
    # 扫描性能指标
    scan_time_ms: float = 0.0
    match_time_ms: float = 0.0
    capture_time_ms: float = 0.0
    total_scan_time_ms: float = 0.0
    
    # 模板和帧相关
    template_count: int = 0
    frame_size_kb: float = 0.0
    fps: float = 0.0
    
    # 自适应控制
    adaptive_interval_ms: int = 0
    
    # IO操作统计
    io_operations: int = 0
    
    # 扩展字段，用于特定场景
    extra_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'timestamp': self.timestamp,
            'cpu_percent': self.cpu_percent,
            'memory_mb': self.memory_mb,
            'scan_time_ms': self.scan_time_ms,
            'match_time_ms': self.match_time_ms,
            'capture_time_ms': self.capture_time_ms,
            'total_scan_time_ms': self.total_scan_time_ms,
            'template_count': self.template_count,
            'frame_size_kb': self.frame_size_kb,
            'fps': self.fps,
            'adaptive_interval_ms': self.adaptive_interval_ms,
            'io_operations': self.io_operations,
            **self.extra_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PerformanceMetrics':
        """从字典创建实例"""
        extra_data = {k: v for k, v in data.items() 
                     if k not in cls.__dataclass_fields__}
        
        return cls(
            timestamp=data.get('timestamp', time.time()),
            cpu_percent=data.get('cpu_percent', 0.0),
            memory_mb=data.get('memory_mb', 0.0),
            scan_time_ms=data.get('scan_time_ms', 0.0),
            match_time_ms=data.get('match_time_ms', 0.0),
            capture_time_ms=data.get('capture_time_ms', 0.0),
            total_scan_time_ms=data.get('total_scan_time_ms', 0.0),
            template_count=data.get('template_count', 0),
            frame_size_kb=data.get('frame_size_kb', 0.0),
            fps=data.get('fps', 0.0),
            adaptive_interval_ms=data.get('adaptive_interval_ms', 0),
            io_operations=data.get('io_operations', 0),
            extra_data=extra_data
        )


@dataclass  
class PerformanceStats:
    """统一的性能统计数据类
    
    整合了原有的多个PerformanceStats定义，提供完整的性能统计功能
    """
    # 操作标识
    operation_name: str = ""
    
    # 基础统计
    total_calls: int = 0
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    min_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    
    # 百分位数统计
    p95_duration_ms: float = 0.0
    p99_duration_ms: float = 0.0
    
    # 扫描相关统计
    avg_scan_time: float = 0.0
    avg_match_time: float = 0.0
    
    # 资源使用统计
    cpu_usage_estimate: float = 0.0
    memory_usage_mb: float = 0.0
    
    # 处理统计
    frames_processed: int = 0
    templates_matched: int = 0
    
    # 更新时间
    last_update: float = 0.0
    
    # 扩展字段
    extra_stats: Dict[str, Any] = field(default_factory=dict)
    
    def update_averages(self):
        """更新平均值计算"""
        if self.total_calls > 0:
            self.avg_duration_ms = self.total_duration_ms / self.total_calls
        
        self.last_update = time.time()
    
    def add_measurement(self, duration_ms: float):
        """添加新的测量值"""
        self.total_calls += 1
        self.total_duration_ms += duration_ms
        
        if self.min_duration_ms == 0.0 or duration_ms < self.min_duration_ms:
            self.min_duration_ms = duration_ms
        
        if duration_ms > self.max_duration_ms:
            self.max_duration_ms = duration_ms
        
        self.update_averages()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'operation_name': self.operation_name,
            'total_calls': self.total_calls,
            'total_duration_ms': self.total_duration_ms,
            'avg_duration_ms': self.avg_duration_ms,
            'min_duration_ms': self.min_duration_ms,
            'max_duration_ms': self.max_duration_ms,
            'p95_duration_ms': self.p95_duration_ms,
            'p99_duration_ms': self.p99_duration_ms,
            'avg_scan_time': self.avg_scan_time,
            'avg_match_time': self.avg_match_time,
            'cpu_usage_estimate': self.cpu_usage_estimate,
            'memory_usage_mb': self.memory_usage_mb,
            'frames_processed': self.frames_processed,
            'templates_matched': self.templates_matched,
            'last_update': self.last_update,
            **self.extra_stats
        }


@dataclass
class PerformanceThresholds:
    """性能阈值配置"""
    # 时间阈值 (毫秒)
    capture_time_warning: float = 50.0
    match_time_warning: float = 100.0
    total_scan_warning: float = 200.0
    
    # 资源阈值
    memory_warning_mb: float = 500.0
    cpu_warning_percent: float = 30.0
    
    # FPS阈值
    fps_warning_min: float = 5.0
    
    # 自定义阈值
    custom_thresholds: Dict[str, float] = field(default_factory=dict)
    
    def get_threshold(self, metric_name: str) -> Optional[float]:
        """获取指定指标的阈值"""
        threshold_map = {
            'capture_time_ms': self.capture_time_warning,
            'match_time_ms': self.match_time_warning,
            'total_scan_time_ms': self.total_scan_warning,
            'memory_mb': self.memory_warning_mb,
            'cpu_percent': self.cpu_warning_percent,
            'fps': self.fps_warning_min
        }
        
        # 优先检查自定义阈值
        if metric_name in self.custom_thresholds:
            return self.custom_thresholds[metric_name]
        
        return threshold_map.get(metric_name)
    
    def is_warning(self, metric_name: str, value: float) -> bool:
        """检查指标值是否超过警告阈值"""
        threshold = self.get_threshold(metric_name)
        if threshold is None:
            return False
        
        # FPS是越低越警告，其他指标是越高越警告
        if metric_name == 'fps':
            return value < threshold
        else:
            return value > threshold


@dataclass
class PerformanceAlert:
    """性能警告信息"""
    timestamp: float = field(default_factory=time.time)
    metric_name: str = ""
    current_value: float = 0.0
    threshold_value: float = 0.0
    severity: str = "warning"  # warning, critical
    message: str = ""
    operation_context: str = ""
    
    def __str__(self) -> str:
        return (f"[{self.severity.upper()}] {self.metric_name}: "
                f"{self.current_value:.2f} > {self.threshold_value:.2f} "
                f"({self.message})")


# 全局默认阈值实例
DEFAULT_THRESHOLDS = PerformanceThresholds()


def create_performance_metrics(**kwargs) -> PerformanceMetrics:
    """便捷函数：创建性能指标实例"""
    return PerformanceMetrics(**kwargs)


def create_performance_stats(operation_name: str, **kwargs) -> PerformanceStats:
    """便捷函数：创建性能统计实例"""
    return PerformanceStats(operation_name=operation_name, **kwargs)


def create_performance_alert(metric_name: str, current_value: float, 
                           threshold_value: float, **kwargs) -> PerformanceAlert:
    """便捷函数：创建性能警告实例"""
    return PerformanceAlert(
        metric_name=metric_name,
        current_value=current_value,
        threshold_value=threshold_value,
        **kwargs
    )

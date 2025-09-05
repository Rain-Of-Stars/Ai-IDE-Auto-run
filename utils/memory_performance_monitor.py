# -*- coding: utf-8 -*-
"""
内存性能监控器 - 监控和优化内存使用的性能管理系统

主要功能：
1. 实时内存使用监控
2. 性能指标收集和分析
3. 智能内存清理和优化
4. 性能报告生成
"""
from __future__ import annotations
import time
import psutil
import threading
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import deque
import numpy as np

from auto_approve.logger_manager import get_logger


@dataclass
class PerformanceMetrics:
    """性能指标"""
    timestamp: float
    memory_usage_mb: float
    memory_percent: float
    cpu_percent: float
    capture_time_ms: float
    template_match_time_ms: float
    total_templates: int
    cache_hit_rate: float
    disk_io_count: int
    memory_io_count: int


class MemoryPerformanceMonitor:
    """内存性能监控器"""
    
    def __init__(self, history_size: int = 1000, monitor_interval: float = 5.0):
        self._logger = get_logger()
        self._history_size = history_size
        self._monitor_interval = monitor_interval
        
        # 性能历史记录
        self._metrics_history: deque = deque(maxlen=history_size)
        self._lock = threading.RLock()
        
        # 计数器
        self._capture_times: deque = deque(maxlen=100)
        self._template_match_times: deque = deque(maxlen=100)
        self._disk_io_count = 0
        self._memory_io_count = 0
        self._cache_hits = 0
        self._cache_misses = 0
        
        # 监控线程
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # 性能阈值
        self._memory_warning_threshold = 80.0  # 内存使用率警告阈值
        self._memory_critical_threshold = 90.0  # 内存使用率严重阈值
        self._capture_time_warning_ms = 100.0  # 捕获时间警告阈值
        
    def start_monitoring(self):
        """启动性能监控"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_worker, daemon=True)
        self._monitor_thread.start()
        self._logger.info("内存性能监控已启动")
    
    def stop_monitoring(self):
        """停止性能监控"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        self._logger.info("内存性能监控已停止")
    
    def record_capture_time(self, capture_time_ms: float):
        """记录捕获时间"""
        with self._lock:
            self._capture_times.append(capture_time_ms)
            
            # 检查性能警告
            if capture_time_ms > self._capture_time_warning_ms:
                self._logger.warning(f"捕获时间过长: {capture_time_ms:.1f}ms")
    
    def record_template_match_time(self, match_time_ms: float):
        """记录模板匹配时间"""
        with self._lock:
            self._template_match_times.append(match_time_ms)
    
    def record_disk_io(self):
        """记录磁盘IO操作"""
        with self._lock:
            self._disk_io_count += 1
    
    def record_memory_io(self):
        """记录内存IO操作"""
        with self._lock:
            self._memory_io_count += 1
    
    def record_cache_hit(self):
        """记录缓存命中"""
        with self._lock:
            self._cache_hits += 1
    
    def record_cache_miss(self):
        """记录缓存未命中"""
        with self._lock:
            self._cache_misses += 1
    
    def _monitor_worker(self):
        """监控工作线程"""
        while self._monitoring:
            try:
                # 收集性能指标
                metrics = self._collect_metrics()
                
                with self._lock:
                    self._metrics_history.append(metrics)
                
                # 检查性能警告
                self._check_performance_warnings(metrics)
                
                time.sleep(self._monitor_interval)
                
            except Exception as e:
                self._logger.error(f"性能监控异常: {e}")
                time.sleep(1.0)
    
    def _collect_metrics(self) -> PerformanceMetrics:
        """收集当前性能指标"""
        try:
            # 系统性能指标
            memory_info = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            with self._lock:
                # 计算平均时间
                avg_capture_time = np.mean(self._capture_times) if self._capture_times else 0.0
                avg_match_time = np.mean(self._template_match_times) if self._template_match_times else 0.0
                
                # 计算缓存命中率
                total_cache_requests = self._cache_hits + self._cache_misses
                cache_hit_rate = self._cache_hits / max(1, total_cache_requests) * 100
                
                # 获取模板管理器状态
                total_templates = 0
                try:
                    from utils.memory_template_manager import get_template_manager
                    template_manager = get_template_manager()
                    stats = template_manager.get_cache_stats()
                    total_templates = stats.get('template_count', 0)
                except Exception:
                    pass
            
            return PerformanceMetrics(
                timestamp=time.time(),
                memory_usage_mb=memory_info.used / (1024 * 1024),
                memory_percent=memory_info.percent,
                cpu_percent=cpu_percent,
                capture_time_ms=avg_capture_time,
                template_match_time_ms=avg_match_time,
                total_templates=total_templates,
                cache_hit_rate=cache_hit_rate,
                disk_io_count=self._disk_io_count,
                memory_io_count=self._memory_io_count
            )
            
        except Exception as e:
            self._logger.error(f"收集性能指标失败: {e}")
            return PerformanceMetrics(
                timestamp=time.time(),
                memory_usage_mb=0, memory_percent=0, cpu_percent=0,
                capture_time_ms=0, template_match_time_ms=0,
                total_templates=0, cache_hit_rate=0,
                disk_io_count=0, memory_io_count=0
            )
    
    def _check_performance_warnings(self, metrics: PerformanceMetrics):
        """检查性能警告"""
        # 内存使用率警告
        if metrics.memory_percent > self._memory_critical_threshold:
            self._logger.error(f"内存使用率严重过高: {metrics.memory_percent:.1f}%")
            self._trigger_memory_cleanup()
        elif metrics.memory_percent > self._memory_warning_threshold:
            self._logger.warning(f"内存使用率过高: {metrics.memory_percent:.1f}%")
        
        # 捕获性能警告
        if metrics.capture_time_ms > self._capture_time_warning_ms:
            self._logger.warning(f"平均捕获时间过长: {metrics.capture_time_ms:.1f}ms")
    
    def _trigger_memory_cleanup(self):
        """触发内存清理"""
        try:
            # 清理模板缓存
            from utils.memory_template_manager import get_template_manager
            template_manager = get_template_manager()
            template_manager._cleanup_old_templates()
            
            # 清理调试图像缓存
            from utils.memory_debug_manager import get_debug_manager
            debug_manager = get_debug_manager()
            debug_manager._cleanup_old_images()
            
            self._logger.info("内存清理已执行")
            
        except Exception as e:
            self._logger.error(f"内存清理失败: {e}")
    
    def get_current_metrics(self) -> Optional[PerformanceMetrics]:
        """获取当前性能指标"""
        return self._collect_metrics()
    
    def get_performance_summary(self, duration_minutes: int = 10) -> Dict[str, Any]:
        """获取性能摘要"""
        with self._lock:
            if not self._metrics_history:
                return {}
            
            # 获取指定时间范围内的指标
            cutoff_time = time.time() - duration_minutes * 60
            recent_metrics = [m for m in self._metrics_history if m.timestamp >= cutoff_time]
            
            if not recent_metrics:
                recent_metrics = list(self._metrics_history)[-10:]  # 至少取最近10个
            
            # 计算统计信息
            memory_usage = [m.memory_usage_mb for m in recent_metrics]
            memory_percent = [m.memory_percent for m in recent_metrics]
            cpu_percent = [m.cpu_percent for m in recent_metrics]
            capture_times = [m.capture_time_ms for m in recent_metrics]
            match_times = [m.template_match_time_ms for m in recent_metrics]
            
            return {
                'duration_minutes': duration_minutes,
                'sample_count': len(recent_metrics),
                'memory_usage_mb': {
                    'current': memory_usage[-1] if memory_usage else 0,
                    'average': np.mean(memory_usage) if memory_usage else 0,
                    'max': np.max(memory_usage) if memory_usage else 0,
                    'min': np.min(memory_usage) if memory_usage else 0
                },
                'memory_percent': {
                    'current': memory_percent[-1] if memory_percent else 0,
                    'average': np.mean(memory_percent) if memory_percent else 0,
                    'max': np.max(memory_percent) if memory_percent else 0
                },
                'cpu_percent': {
                    'average': np.mean(cpu_percent) if cpu_percent else 0,
                    'max': np.max(cpu_percent) if cpu_percent else 0
                },
                'capture_time_ms': {
                    'average': np.mean(capture_times) if capture_times else 0,
                    'max': np.max(capture_times) if capture_times else 0,
                    'min': np.min(capture_times) if capture_times else 0
                },
                'template_match_time_ms': {
                    'average': np.mean(match_times) if match_times else 0,
                    'max': np.max(match_times) if match_times else 0
                },
                'cache_performance': {
                    'hit_rate_percent': recent_metrics[-1].cache_hit_rate if recent_metrics else 0,
                    'total_templates': recent_metrics[-1].total_templates if recent_metrics else 0
                },
                'io_performance': {
                    'disk_io_count': self._disk_io_count,
                    'memory_io_count': self._memory_io_count,
                    'memory_io_ratio': self._memory_io_count / max(1, self._disk_io_count + self._memory_io_count) * 100
                }
            }
    
    def export_performance_data(self, output_file: str) -> bool:
        """导出性能数据"""
        try:
            import json
            
            with self._lock:
                data = {
                    'export_time': time.time(),
                    'metrics_count': len(self._metrics_history),
                    'metrics': [asdict(m) for m in self._metrics_history]
                }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self._logger.info(f"性能数据已导出: {output_file}")
            return True
            
        except Exception as e:
            self._logger.error(f"导出性能数据失败: {e}")
            return False
    
    def reset_counters(self):
        """重置计数器"""
        with self._lock:
            self._disk_io_count = 0
            self._memory_io_count = 0
            self._cache_hits = 0
            self._cache_misses = 0
            self._capture_times.clear()
            self._template_match_times.clear()
        self._logger.info("性能计数器已重置")


# 全局实例
_performance_monitor: Optional[MemoryPerformanceMonitor] = None


def get_performance_monitor() -> MemoryPerformanceMonitor:
    """获取全局性能监控器实例"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = MemoryPerformanceMonitor()
    return _performance_monitor

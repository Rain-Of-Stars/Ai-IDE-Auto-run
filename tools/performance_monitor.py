# -*- coding: utf-8 -*-
"""
性能监控工具 - 诊断卡顿问题

用于实时监控扫描性能，识别性能瓶颈：
- 帧捕获耗时
- 模板匹配耗时  
- 内存使用情况
- CPU使用率估算
- IO操作统计
"""

import time
import threading
import psutil
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from auto_approve.logger_manager import get_logger


@dataclass
class PerformanceMetrics:
    """性能指标数据"""
    timestamp: float = field(default_factory=time.time)
    capture_time_ms: float = 0.0
    match_time_ms: float = 0.0
    total_scan_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_percent: float = 0.0
    template_count: int = 0
    frame_size_kb: float = 0.0
    io_operations: int = 0


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.metrics_history: List[PerformanceMetrics] = []
        self.current_metrics = PerformanceMetrics()
        self._lock = threading.RLock()
        self._logger = get_logger()
        
        # 进程监控
        self._process = psutil.Process()
        self._last_cpu_time = 0.0
        self._last_check_time = 0.0
        
        # 性能阈值
        self.thresholds = {
            'capture_time_ms': 50.0,      # 捕获超过50ms警告
            'match_time_ms': 100.0,       # 匹配超过100ms警告
            'total_scan_time_ms': 200.0,  # 总扫描超过200ms警告
            'memory_usage_mb': 500.0,     # 内存超过500MB警告
            'cpu_percent': 30.0           # CPU超过30%警告
        }
        
        # 统计计数器
        self.stats = {
            'total_scans': 0,
            'slow_captures': 0,
            'slow_matches': 0,
            'slow_scans': 0,
            'memory_warnings': 0,
            'cpu_warnings': 0
        }
    
    def start_scan(self) -> str:
        """开始扫描计时，返回扫描ID"""
        scan_id = f"scan_{int(time.time() * 1000)}"
        with self._lock:
            self.current_metrics = PerformanceMetrics()
            self.current_metrics.timestamp = time.time()
        return scan_id
    
    def record_capture_time(self, duration_ms: float, frame_size_bytes: int = 0):
        """记录捕获耗时"""
        with self._lock:
            self.current_metrics.capture_time_ms = duration_ms
            self.current_metrics.frame_size_kb = frame_size_bytes / 1024.0
            
            if duration_ms > self.thresholds['capture_time_ms']:
                self.stats['slow_captures'] += 1
                self._logger.warning(f"捕获耗时过长: {duration_ms:.1f}ms")
    
    def record_match_time(self, duration_ms: float, template_count: int = 0):
        """记录匹配耗时"""
        with self._lock:
            self.current_metrics.match_time_ms = duration_ms
            self.current_metrics.template_count = template_count
            
            if duration_ms > self.thresholds['match_time_ms']:
                self.stats['slow_matches'] += 1
                self._logger.warning(f"模板匹配耗时过长: {duration_ms:.1f}ms (模板数: {template_count})")
    
    def record_io_operation(self):
        """记录IO操作"""
        with self._lock:
            self.current_metrics.io_operations += 1
    
    def finish_scan(self, scan_id: str):
        """完成扫描，计算总耗时并更新统计"""
        with self._lock:
            # 计算总耗时
            total_time = (time.time() - self.current_metrics.timestamp) * 1000
            self.current_metrics.total_scan_time_ms = total_time
            
            # 更新系统资源使用情况
            self._update_system_metrics()
            
            # 检查性能阈值
            self._check_thresholds()
            
            # 保存到历史记录
            self.metrics_history.append(self.current_metrics)
            if len(self.metrics_history) > self.max_history:
                self.metrics_history = self.metrics_history[-self.max_history:]
            
            # 更新统计
            self.stats['total_scans'] += 1
            
            if total_time > self.thresholds['total_scan_time_ms']:
                self.stats['slow_scans'] += 1
                self._logger.warning(f"扫描总耗时过长: {total_time:.1f}ms")
    
    def _update_system_metrics(self):
        """更新系统资源使用情况"""
        try:
            # 内存使用
            memory_info = self._process.memory_info()
            self.current_metrics.memory_usage_mb = memory_info.rss / 1024 / 1024
            
            # CPU使用率（简单估算）
            current_time = time.time()
            if self._last_check_time > 0:
                time_delta = current_time - self._last_check_time
                if time_delta > 1.0:  # 每秒更新一次CPU统计
                    try:
                        cpu_percent = self._process.cpu_percent()
                        self.current_metrics.cpu_percent = cpu_percent
                        self._last_check_time = current_time
                    except:
                        pass
            else:
                self._last_check_time = current_time
                
        except Exception as e:
            self._logger.debug(f"更新系统指标失败: {e}")
    
    def _check_thresholds(self):
        """检查性能阈值"""
        metrics = self.current_metrics
        
        if metrics.memory_usage_mb > self.thresholds['memory_usage_mb']:
            self.stats['memory_warnings'] += 1
            self._logger.warning(f"内存使用过高: {metrics.memory_usage_mb:.1f}MB")
        
        if metrics.cpu_percent > self.thresholds['cpu_percent']:
            self.stats['cpu_warnings'] += 1
            self._logger.warning(f"CPU使用率过高: {metrics.cpu_percent:.1f}%")
    
    def get_performance_summary(self) -> Dict:
        """获取性能摘要"""
        with self._lock:
            if not self.metrics_history:
                return {"error": "暂无性能数据"}
            
            recent_metrics = self.metrics_history[-10:]  # 最近10次扫描
            
            avg_capture = sum(m.capture_time_ms for m in recent_metrics) / len(recent_metrics)
            avg_match = sum(m.match_time_ms for m in recent_metrics) / len(recent_metrics)
            avg_total = sum(m.total_scan_time_ms for m in recent_metrics) / len(recent_metrics)
            avg_memory = sum(m.memory_usage_mb for m in recent_metrics) / len(recent_metrics)
            
            return {
                "recent_performance": {
                    "avg_capture_time_ms": round(avg_capture, 2),
                    "avg_match_time_ms": round(avg_match, 2),
                    "avg_total_time_ms": round(avg_total, 2),
                    "avg_memory_mb": round(avg_memory, 2),
                    "current_cpu_percent": round(self.current_metrics.cpu_percent, 1)
                },
                "statistics": self.stats.copy(),
                "thresholds": self.thresholds.copy(),
                "total_history_count": len(self.metrics_history)
            }
    
    def get_performance_issues(self) -> List[str]:
        """获取当前性能问题列表"""
        issues = []
        
        if not self.metrics_history:
            return ["暂无性能数据"]
        
        recent = self.metrics_history[-5:]  # 最近5次
        
        # 检查捕获性能
        avg_capture = sum(m.capture_time_ms for m in recent) / len(recent)
        if avg_capture > self.thresholds['capture_time_ms']:
            issues.append(f"帧捕获耗时过长 (平均 {avg_capture:.1f}ms)")
        
        # 检查匹配性能
        avg_match = sum(m.match_time_ms for m in recent) / len(recent)
        if avg_match > self.thresholds['match_time_ms']:
            issues.append(f"模板匹配耗时过长 (平均 {avg_match:.1f}ms)")
        
        # 检查总扫描时间
        avg_total = sum(m.total_scan_time_ms for m in recent) / len(recent)
        if avg_total > self.thresholds['total_scan_time_ms']:
            issues.append(f"扫描总耗时过长 (平均 {avg_total:.1f}ms)")
        
        # 检查内存使用
        current_memory = self.current_metrics.memory_usage_mb
        if current_memory > self.thresholds['memory_usage_mb']:
            issues.append(f"内存使用过高 ({current_memory:.1f}MB)")
        
        # 检查CPU使用
        current_cpu = self.current_metrics.cpu_percent
        if current_cpu > self.thresholds['cpu_percent']:
            issues.append(f"CPU使用率过高 ({current_cpu:.1f}%)")
        
        # 检查IO操作频率
        avg_io = sum(m.io_operations for m in recent) / len(recent)
        if avg_io > 5:  # 每次扫描超过5次IO操作
            issues.append(f"IO操作过于频繁 (平均 {avg_io:.1f}次/扫描)")
        
        if not issues:
            issues.append("性能正常")
        
        return issues
    
    def reset_stats(self):
        """重置统计数据"""
        with self._lock:
            self.stats = {key: 0 for key in self.stats}
            self.metrics_history.clear()
            self._logger.info("性能统计已重置")


# 全局性能监控器实例
_global_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor


def print_performance_report():
    """打印性能报告"""
    monitor = get_performance_monitor()
    summary = monitor.get_performance_summary()
    issues = monitor.get_performance_issues()
    
    print("\n" + "="*50)
    print("性能监控报告")
    print("="*50)
    
    if "error" in summary:
        print(f"❌ {summary['error']}")
        return
    
    recent = summary["recent_performance"]
    print(f"📊 最近性能指标:")
    print(f"   帧捕获耗时: {recent['avg_capture_time_ms']:.1f}ms")
    print(f"   模板匹配耗时: {recent['avg_match_time_ms']:.1f}ms")
    print(f"   总扫描耗时: {recent['avg_total_time_ms']:.1f}ms")
    print(f"   内存使用: {recent['avg_memory_mb']:.1f}MB")
    print(f"   CPU使用率: {recent['current_cpu_percent']:.1f}%")
    
    stats = summary["statistics"]
    print(f"\n📈 统计信息:")
    print(f"   总扫描次数: {stats['total_scans']}")
    print(f"   慢捕获次数: {stats['slow_captures']}")
    print(f"   慢匹配次数: {stats['slow_matches']}")
    print(f"   慢扫描次数: {stats['slow_scans']}")
    
    print(f"\n⚠️  当前问题:")
    for issue in issues:
        print(f"   • {issue}")
    
    print("="*50)


if __name__ == "__main__":
    print_performance_report()

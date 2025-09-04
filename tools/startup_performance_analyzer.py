# -*- coding: utf-8 -*-
"""
启动性能分析器 - 专门分析UI初始卡顿问题
通过时间测量和性能监控来定位卡顿原因
"""
from __future__ import annotations
import os
import sys
import time
import psutil
import threading
from typing import Dict, List, Tuple
from dataclasses import dataclass

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

@dataclass
class PerformanceMetric:
    """性能指标数据类"""
    timestamp: float
    cpu_percent: float
    memory_mb: float
    operation: str
    duration_ms: float = 0.0

class StartupPerformanceAnalyzer:
    """启动性能分析器"""
    
    def __init__(self):
        self.metrics: List[PerformanceMetric] = []
        self.start_time = time.time()
        self.monitoring = False
        self.monitor_thread = None
        
    def start_monitoring(self):
        """开始性能监控"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("🔍 启动性能监控...")
        
    def stop_monitoring(self):
        """停止性能监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        print("⏹️ 停止性能监控")
        
    def _monitor_loop(self):
        """监控循环"""
        process = psutil.Process()
        while self.monitoring:
            try:
                cpu_percent = process.cpu_percent()
                memory_mb = process.memory_info().rss / 1024 / 1024
                
                metric = PerformanceMetric(
                    timestamp=time.time() - self.start_time,
                    cpu_percent=cpu_percent,
                    memory_mb=memory_mb,
                    operation="background_monitor"
                )
                self.metrics.append(metric)
                
                time.sleep(0.1)  # 100ms间隔监控
            except Exception as e:
                print(f"监控异常: {e}")
                break
                
    def measure_operation(self, operation_name: str):
        """测量操作性能的装饰器"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                
                # 记录开始指标
                try:
                    process = psutil.Process()
                    cpu_before = process.cpu_percent()
                    memory_before = process.memory_info().rss / 1024 / 1024
                except:
                    cpu_before = 0
                    memory_before = 0
                
                print(f"⏱️ 开始执行: {operation_name}")
                
                # 执行操作
                result = func(*args, **kwargs)
                
                # 记录结束指标
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                
                try:
                    process = psutil.Process()
                    cpu_after = process.cpu_percent()
                    memory_after = process.memory_info().rss / 1024 / 1024
                except:
                    cpu_after = 0
                    memory_after = 0
                
                metric = PerformanceMetric(
                    timestamp=end_time - self.start_time,
                    cpu_percent=cpu_after,
                    memory_mb=memory_after,
                    operation=operation_name,
                    duration_ms=duration_ms
                )
                self.metrics.append(metric)
                
                # 输出性能信息
                if duration_ms > 100:  # 超过100ms的操作标记为慢
                    print(f"🐌 {operation_name}: {duration_ms:.1f}ms (CPU: {cpu_after:.1f}%, 内存: {memory_after:.1f}MB)")
                else:
                    print(f"✅ {operation_name}: {duration_ms:.1f}ms")
                
                return result
            return wrapper
        return decorator
        
    def analyze_startup_bottlenecks(self) -> Dict[str, any]:
        """分析启动瓶颈"""
        if not self.metrics:
            return {"error": "没有性能数据"}
            
        # 按操作分组分析
        operation_stats = {}
        for metric in self.metrics:
            if metric.operation not in operation_stats:
                operation_stats[metric.operation] = {
                    "count": 0,
                    "total_duration": 0,
                    "max_duration": 0,
                    "avg_cpu": 0,
                    "max_memory": 0
                }
            
            stats = operation_stats[metric.operation]
            stats["count"] += 1
            stats["total_duration"] += metric.duration_ms
            stats["max_duration"] = max(stats["max_duration"], metric.duration_ms)
            stats["avg_cpu"] += metric.cpu_percent
            stats["max_memory"] = max(stats["max_memory"], metric.memory_mb)
        
        # 计算平均值
        for stats in operation_stats.values():
            if stats["count"] > 0:
                stats["avg_cpu"] /= stats["count"]
                stats["avg_duration"] = stats["total_duration"] / stats["count"]
        
        # 找出最慢的操作
        slow_operations = []
        for op_name, stats in operation_stats.items():
            if stats["max_duration"] > 200:  # 超过200ms
                slow_operations.append((op_name, stats["max_duration"]))
        
        slow_operations.sort(key=lambda x: x[1], reverse=True)
        
        return {
            "operation_stats": operation_stats,
            "slow_operations": slow_operations,
            "total_startup_time": max(m.timestamp for m in self.metrics) if self.metrics else 0,
            "peak_memory": max(m.memory_mb for m in self.metrics) if self.metrics else 0,
            "peak_cpu": max(m.cpu_percent for m in self.metrics) if self.metrics else 0
        }
        
    def generate_report(self) -> str:
        """生成性能报告"""
        analysis = self.analyze_startup_bottlenecks()
        
        if "error" in analysis:
            return f"❌ 分析失败: {analysis['error']}"
        
        report = []
        report.append("📊 启动性能分析报告")
        report.append("=" * 50)
        
        # 总体统计
        report.append(f"🕐 总启动时间: {analysis['total_startup_time']:.2f}秒")
        report.append(f"🧠 峰值内存: {analysis['peak_memory']:.1f}MB")
        report.append(f"⚡峰值CPU: {analysis['peak_cpu']:.1f}%")
        report.append("")
        
        # 慢操作分析
        if analysis['slow_operations']:
            report.append("🐌 发现的性能瓶颈:")
            for op_name, duration in analysis['slow_operations'][:5]:  # 显示前5个最慢的
                report.append(f"   • {op_name}: {duration:.1f}ms")
            report.append("")
        
        # 操作统计
        report.append("📈 各操作性能统计:")
        for op_name, stats in analysis['operation_stats'].items():
            if stats['count'] > 0 and op_name != "background_monitor":
                report.append(f"   • {op_name}:")
                report.append(f"     - 平均耗时: {stats['avg_duration']:.1f}ms")
                report.append(f"     - 最大耗时: {stats['max_duration']:.1f}ms")
                report.append(f"     - 平均CPU: {stats['avg_cpu']:.1f}%")
                report.append(f"     - 峰值内存: {stats['max_memory']:.1f}MB")
        
        # 优化建议
        report.append("")
        report.append("💡 优化建议:")
        
        if analysis['peak_memory'] > 200:
            report.append("   • 内存使用较高，考虑延迟加载非关键模块")
            
        if analysis['peak_cpu'] > 50:
            report.append("   • CPU使用较高，检查是否有同步阻塞操作")
            
        for op_name, duration in analysis['slow_operations'][:3]:
            if duration > 500:
                report.append(f"   • 优化 {op_name} 操作，当前耗时 {duration:.1f}ms")
        
        return "\n".join(report)

def analyze_main_startup():
    """分析主程序启动性能"""
    analyzer = StartupPerformanceAnalyzer()
    analyzer.start_monitoring()
    
    try:
        # 模拟主程序启动过程
        print("🚀 开始分析主程序启动性能...")
        
        # 测量各个启动阶段
        @analyzer.measure_operation("导入基础模块")
        def import_basic_modules():
            import warnings
            import ctypes
            time.sleep(0.05)  # 模拟导入时间
            
        @analyzer.measure_operation("设置环境变量")
        def setup_environment():
            os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.window=false")
            os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
            time.sleep(0.02)
            
        @analyzer.measure_operation("导入Qt模块")
        def import_qt_modules():
            try:
                from PySide6 import QtWidgets, QtGui, QtCore
                from PySide6.QtNetwork import QLocalServer, QLocalSocket
                time.sleep(0.1)  # Qt导入通常较慢
            except ImportError:
                print("⚠️ 无法导入PySide6，跳过Qt模块测试")
                
        @analyzer.measure_operation("导入项目模块")
        def import_project_modules():
            try:
                from auto_approve.config_manager import load_config
                from auto_approve.logger_manager import get_logger
                from auto_approve.menu_icons import create_menu_icon
                time.sleep(0.08)
            except ImportError as e:
                print(f"⚠️ 导入项目模块失败: {e}")
                
        @analyzer.measure_operation("加载配置")
        def load_configuration():
            try:
                from auto_approve.config_manager import load_config
                config = load_config()
                time.sleep(0.03)
            except Exception as e:
                print(f"⚠️ 加载配置失败: {e}")
                
        @analyzer.measure_operation("创建菜单图标")
        def create_menu_icons():
            try:
                from auto_approve.menu_icons import create_menu_icon
                # 模拟创建多个图标
                for icon_type in ["status", "play", "stop", "settings", "quit"]:
                    icon = create_menu_icon(icon_type, 20, "#FF4444")
                time.sleep(0.05)
            except Exception as e:
                print(f"⚠️ 创建菜单图标失败: {e}")
                
        @analyzer.measure_operation("应用主题样式")
        def apply_theme():
            time.sleep(0.04)  # 模拟主题应用时间
            
        # 执行各个阶段
        import_basic_modules()
        setup_environment()
        import_qt_modules()
        import_project_modules()
        load_configuration()
        create_menu_icons()
        apply_theme()
        
        # 等待一段时间收集更多监控数据
        time.sleep(1.0)
        
    finally:
        analyzer.stop_monitoring()
    
    # 生成并显示报告
    report = analyzer.generate_report()
    print("\n" + report)
    
    return analyzer

if __name__ == "__main__":
    print("🔍 启动性能分析器")
    print("=" * 50)
    
    analyzer = analyze_main_startup()
    
    print("\n✅ 分析完成")
    print("💡 提示: 如果发现性能瓶颈，可以针对性优化相应模块")

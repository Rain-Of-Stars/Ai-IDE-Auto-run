# -*- coding: utf-8 -*-
"""
性能监控模块

包含所有性能相关功能：
- 性能数据类型定义
- 性能监控器
- 性能优化器
- GUI性能监控
- 配置优化
"""

# 导出性能相关类
try:
    from ..performance_types import (
        PerformanceMetrics, PerformanceStats, PerformanceThresholds,
        PerformanceAlert, DEFAULT_THRESHOLDS,
        create_performance_metrics, create_performance_stats, create_performance_alert
    )
    from ..performance_monitor import PerformanceMonitor
    from ..performance_optimizer import PerformanceOptimizer
    from ..performance_config import get_performance_config, apply_performance_optimizations
    from ..config_optimizer import ConfigOptimizer
    from ..gui_performance_monitor import get_gui_performance_monitor, start_gui_monitoring
    from ..gui_responsiveness_manager import get_gui_responsiveness_manager
except ImportError:
    # 如果文件还没有移动，使用原始导入
    pass

__all__ = [
    # 数据类型
    'PerformanceMetrics', 'PerformanceStats', 'PerformanceThresholds', 'PerformanceAlert',
    'DEFAULT_THRESHOLDS',
    # 便捷函数
    'create_performance_metrics', 'create_performance_stats', 'create_performance_alert',
    # 监控器
    'PerformanceMonitor', 'PerformanceOptimizer',
    # 配置
    'get_performance_config', 'apply_performance_optimizations', 'ConfigOptimizer',
    # GUI监控
    'get_gui_performance_monitor', 'start_gui_monitoring', 'get_gui_responsiveness_manager'
]

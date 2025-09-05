# -*- coding: utf-8 -*-
"""
内存优化工具模块

包含所有内存优化相关功能：
- 内存配置管理
- 内存调试管理
- 内存优化管理
- 内存性能监控
- 内存模板管理
"""

# 导出内存优化相关类
try:
    from ..memory_config_manager import MemoryConfigManager
    from ..memory_debug_manager import MemoryDebugManager
    from ..memory_optimization_manager import MemoryOptimizationManager
    from ..memory_performance_monitor import MemoryPerformanceMonitor
    from ..memory_template_manager import MemoryTemplateManager
except ImportError:
    # 如果文件还没有移动，使用原始导入
    pass

__all__ = [
    'MemoryConfigManager', 'MemoryDebugManager', 'MemoryOptimizationManager',
    'MemoryPerformanceMonitor', 'MemoryTemplateManager'
]

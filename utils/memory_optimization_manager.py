# -*- coding: utf-8 -*-
"""
内存优化管理器 - 统一的内存优化和磁盘IO避免系统

主要功能：
1. 统一管理所有内存优化组件
2. 提供简单的API接口
3. 自动化的性能监控和优化
4. 系统资源的智能调度
"""
from __future__ import annotations
import time
import threading
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from auto_approve.logger_manager import get_logger


@dataclass
class OptimizationStats:
    """优化统计信息"""
    template_cache_enabled: bool
    debug_cache_enabled: bool
    config_cache_enabled: bool
    performance_monitoring_enabled: bool
    total_memory_saved_mb: float
    disk_io_avoided_count: int
    cache_hit_rate_percent: float
    optimization_level: str


class MemoryOptimizationManager:
    """内存优化管理器 - 统一的内存优化系统"""
    
    def __init__(self):
        self._logger = get_logger()
        self._initialized = False
        self._optimization_level = "balanced"  # conservative, balanced, aggressive
        self._lock = threading.RLock()
        
        # 组件引用
        self._template_manager = None
        self._debug_manager = None
        self._config_manager = None
        self._performance_monitor = None
        
        # 统计信息
        self._disk_io_avoided = 0
        self._memory_saved_mb = 0.0
        self._start_time = time.time()
        
    def initialize(self, optimization_level: str = "balanced") -> bool:
        """
        初始化内存优化系统
        
        Args:
            optimization_level: 优化级别 (conservative, balanced, aggressive)
            
        Returns:
            是否初始化成功
        """
        if self._initialized:
            return True
        
        try:
            self._optimization_level = optimization_level
            
            # 初始化各个组件
            self._init_template_manager()
            self._init_debug_manager()
            self._init_config_manager()
            self._init_performance_monitor()
            
            self._initialized = True
            self._logger.info(f"内存优化系统已初始化 (级别: {optimization_level})")
            return True
            
        except Exception as e:
            self._logger.error(f"内存优化系统初始化失败: {e}")
            return False
    
    def _init_template_manager(self):
        """初始化模板管理器"""
        try:
            from utils.memory_template_manager import get_template_manager
            self._template_manager = get_template_manager()
            
            # 根据优化级别设置参数
            if self._optimization_level == "aggressive":
                self._template_manager._max_memory_mb = 200
            elif self._optimization_level == "balanced":
                self._template_manager._max_memory_mb = 100
            else:  # conservative
                self._template_manager._max_memory_mb = 50
                
            self._logger.debug("模板管理器已初始化")
            
        except Exception as e:
            self._logger.error(f"模板管理器初始化失败: {e}")
    
    def _init_debug_manager(self):
        """初始化调试管理器"""
        try:
            from utils.memory_debug_manager import get_debug_manager
            self._debug_manager = get_debug_manager()
            
            # 根据优化级别设置参数
            if self._optimization_level == "aggressive":
                self._debug_manager._max_memory_mb = 100
                self._debug_manager._max_images = 200
            elif self._optimization_level == "balanced":
                self._debug_manager._max_memory_mb = 50
                self._debug_manager._max_images = 100
            else:  # conservative
                self._debug_manager._max_memory_mb = 25
                self._debug_manager._max_images = 50
            
            # 默认启用调试缓存
            self._debug_manager.enable(True)
            self._logger.debug("调试管理器已初始化")
            
        except Exception as e:
            self._logger.error(f"调试管理器初始化失败: {e}")
    
    def _init_config_manager(self):
        """初始化配置管理器"""
        try:
            from utils.memory_config_manager import get_config_manager
            self._config_manager = get_config_manager()
            
            # 根据优化级别设置自动保存间隔
            if self._optimization_level == "aggressive":
                self._config_manager._auto_save_interval = 60.0  # 1分钟
            elif self._optimization_level == "balanced":
                self._config_manager._auto_save_interval = 30.0  # 30秒
            else:  # conservative
                self._config_manager._auto_save_interval = 15.0  # 15秒
                
            self._logger.debug("配置管理器已初始化")
            
        except Exception as e:
            self._logger.error(f"配置管理器初始化失败: {e}")
    
    def _init_performance_monitor(self):
        """初始化性能监控器"""
        try:
            from utils.memory_performance_monitor import get_performance_monitor
            self._performance_monitor = get_performance_monitor()
            
            # 根据优化级别设置监控间隔
            if self._optimization_level == "aggressive":
                self._performance_monitor._monitor_interval = 2.0  # 2秒
            elif self._optimization_level == "balanced":
                self._performance_monitor._monitor_interval = 5.0  # 5秒
            else:  # conservative
                self._performance_monitor._monitor_interval = 10.0  # 10秒
            
            # 启动性能监控
            self._performance_monitor.start_monitoring()
            self._logger.debug("性能监控器已初始化")
            
        except Exception as e:
            self._logger.error(f"性能监控器初始化失败: {e}")
    
    def load_templates(self, template_paths: List[str]) -> int:
        """加载模板到内存缓存"""
        if not self._initialized or not self._template_manager:
            return 0
        
        try:
            loaded_count = self._template_manager.load_templates(template_paths)
            if loaded_count > 0:
                self._disk_io_avoided += loaded_count
                # 估算节省的内存（每次避免磁盘读取约节省1-5MB）
                self._memory_saved_mb += loaded_count * 2.0
            return loaded_count
            
        except Exception as e:
            self._logger.error(f"加载模板失败: {e}")
            return 0
    
    def get_templates(self, template_paths: List[str]) -> List[Tuple[Any, Tuple[int, int]]]:
        """获取模板数据（纯内存操作）"""
        if not self._initialized or not self._template_manager:
            return []
        
        try:
            templates = self._template_manager.get_templates(template_paths)
            if templates:
                self._performance_monitor.record_memory_io()
            return templates
            
        except Exception as e:
            self._logger.error(f"获取模板失败: {e}")
            return []
    
    def save_debug_image(self, image: Any, name: str, category: str = "general") -> Optional[str]:
        """保存调试图像到内存"""
        if not self._initialized or not self._debug_manager:
            return None
        
        try:
            image_id = self._debug_manager.save_debug_image(image, name, category)
            if image_id:
                self._disk_io_avoided += 1
                self._memory_saved_mb += 0.5  # 估算每张图片节省0.5MB磁盘IO
                self._performance_monitor.record_memory_io()
            return image_id
            
        except Exception as e:
            self._logger.error(f"保存调试图像失败: {e}")
            return None
    
    def load_config(self, config_path: str, default_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """加载配置（内存缓存）"""
        if not self._initialized or not self._config_manager:
            return default_config or {}
        
        try:
            config = self._config_manager.load_config(config_path, default_config)
            self._performance_monitor.record_memory_io()
            return config
            
        except Exception as e:
            self._logger.error(f"加载配置失败: {e}")
            return default_config or {}
    
    def set_config(self, config_path: str, key: str, value: Any, immediate_save: bool = False) -> bool:
        """设置配置值（内存操作）"""
        if not self._initialized or not self._config_manager:
            return False
        
        try:
            success = self._config_manager.set_config(config_path, key, value, immediate_save)
            if success and not immediate_save:
                self._disk_io_avoided += 1  # 延迟写入避免了一次磁盘IO
            return success
            
        except Exception as e:
            self._logger.error(f"设置配置失败: {e}")
            return False
    
    def record_capture_time(self, capture_time_ms: float):
        """记录捕获时间"""
        if self._performance_monitor:
            self._performance_monitor.record_capture_time(capture_time_ms)
    
    def record_template_match_time(self, match_time_ms: float):
        """记录模板匹配时间"""
        if self._performance_monitor:
            self._performance_monitor.record_template_match_time(match_time_ms)
    
    def get_optimization_stats(self) -> OptimizationStats:
        """获取优化统计信息"""
        try:
            # 获取各组件状态
            template_enabled = self._template_manager is not None
            debug_enabled = self._debug_manager is not None and self._debug_manager._enabled
            config_enabled = self._config_manager is not None
            monitor_enabled = self._performance_monitor is not None and self._performance_monitor._monitoring
            
            # 计算缓存命中率
            cache_hit_rate = 0.0
            if self._template_manager:
                stats = self._template_manager.get_cache_stats()
                cache_hit_rate = stats.get('hit_rate_percent', 0.0)
            
            return OptimizationStats(
                template_cache_enabled=template_enabled,
                debug_cache_enabled=debug_enabled,
                config_cache_enabled=config_enabled,
                performance_monitoring_enabled=monitor_enabled,
                total_memory_saved_mb=self._memory_saved_mb,
                disk_io_avoided_count=self._disk_io_avoided,
                cache_hit_rate_percent=cache_hit_rate,
                optimization_level=self._optimization_level
            )
            
        except Exception as e:
            self._logger.error(f"获取优化统计失败: {e}")
            return OptimizationStats(
                template_cache_enabled=False,
                debug_cache_enabled=False,
                config_cache_enabled=False,
                performance_monitoring_enabled=False,
                total_memory_saved_mb=0.0,
                disk_io_avoided_count=0,
                cache_hit_rate_percent=0.0,
                optimization_level="unknown"
            )
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        if not self._performance_monitor:
            return {}
        
        try:
            summary = self._performance_monitor.get_performance_summary()
            
            # 添加优化相关信息
            summary['optimization'] = {
                'level': self._optimization_level,
                'uptime_hours': (time.time() - self._start_time) / 3600,
                'disk_io_avoided': self._disk_io_avoided,
                'memory_saved_mb': self._memory_saved_mb
            }
            
            return summary
            
        except Exception as e:
            self._logger.error(f"获取性能摘要失败: {e}")
            return {}
    
    def export_debug_images(self, output_dir: str, category: Optional[str] = None) -> int:
        """导出调试图像到磁盘"""
        if not self._debug_manager:
            return 0
        
        try:
            return self._debug_manager.export_to_disk(output_dir, category)
        except Exception as e:
            self._logger.error(f"导出调试图像失败: {e}")
            return 0
    
    def cleanup(self):
        """清理资源"""
        try:
            if self._performance_monitor:
                self._performance_monitor.stop_monitoring()
            
            if self._template_manager:
                self._template_manager.clear_cache()
            
            if self._debug_manager:
                self._debug_manager.clear_all()
            
            if self._config_manager:
                self._config_manager.clear_cache()
            
            self._initialized = False
            self._logger.info("内存优化系统已清理")
            
        except Exception as e:
            self._logger.error(f"清理内存优化系统失败: {e}")


# 全局实例
_optimization_manager: Optional[MemoryOptimizationManager] = None


def get_optimization_manager() -> MemoryOptimizationManager:
    """获取全局内存优化管理器实例"""
    global _optimization_manager
    if _optimization_manager is None:
        _optimization_manager = MemoryOptimizationManager()
    return _optimization_manager


def initialize_memory_optimization(optimization_level: str = "balanced") -> bool:
    """初始化内存优化系统的便捷函数"""
    manager = get_optimization_manager()
    return manager.initialize(optimization_level)

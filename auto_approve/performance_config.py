# -*- coding: utf-8 -*-
"""
性能配置管理器 - 根据系统性能自动调整应用设置
"""
from __future__ import annotations
import psutil
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from auto_approve.logger_manager import get_logger


@dataclass
class PerformanceProfile:
    """性能配置档案"""
    name: str
    description: str
    # UI更新频率设置
    status_update_interval: float  # 状态更新间隔（秒）
    tooltip_update_interval: float  # tooltip更新间隔（秒）
    ui_batch_delay: int  # UI批量更新延迟（毫秒）
    
    # 监控设置
    performance_monitor_interval: float  # 性能监控间隔（秒）
    performance_history_size: int  # 性能历史记录大小
    
    # 动画设置
    animations_enabled: bool  # 是否启用动画
    animation_duration: int  # 动画持续时间（毫秒）
    
    # 扫描设置
    scan_interval_multiplier: float  # 扫描间隔倍数
    template_cache_size: int  # 模板缓存大小
    
    # 其他优化
    enable_debug_images: bool  # 是否启用调试图像保存
    max_worker_threads: int  # 最大工作线程数


class PerformanceConfigManager:
    """性能配置管理器"""
    
    # 预定义的性能档案
    PROFILES = {
        'high_performance': PerformanceProfile(
            name="高性能",
            description="适用于高性能设备，启用所有功能",
            status_update_interval=0.5,
            tooltip_update_interval=1.0,
            ui_batch_delay=50,
            performance_monitor_interval=1.0,
            performance_history_size=300,
            animations_enabled=True,
            animation_duration=300,
            scan_interval_multiplier=1.0,
            template_cache_size=50,
            enable_debug_images=True,
            max_worker_threads=4
        ),
        'balanced': PerformanceProfile(
            name="平衡",
            description="平衡性能和资源占用",
            status_update_interval=1.0,
            tooltip_update_interval=2.0,
            ui_batch_delay=100,
            performance_monitor_interval=5.0,
            performance_history_size=60,
            animations_enabled=True,
            animation_duration=150,
            scan_interval_multiplier=1.0,
            template_cache_size=20,
            enable_debug_images=False,
            max_worker_threads=2
        ),
        'low_resource': PerformanceProfile(
            name="低资源",
            description="适用于低性能设备，最小化资源占用",
            status_update_interval=5.0,  # 进一步减少更新频率
            tooltip_update_interval=10.0,  # 减少tooltip更新
            ui_batch_delay=300,  # 增加批量延迟
            performance_monitor_interval=30.0,  # 减少监控频率
            performance_history_size=10,  # 减少历史记录
            animations_enabled=False,
            animation_duration=0,  # 完全禁用动画
            scan_interval_multiplier=2.0,  # 增加扫描间隔
            template_cache_size=3,  # 减少缓存大小
            enable_debug_images=False,
            max_worker_threads=1
        ),
        'minimal': PerformanceProfile(
            name="极简",
            description="极简模式，最低资源占用",
            status_update_interval=10.0,
            tooltip_update_interval=30.0,
            ui_batch_delay=500,
            performance_monitor_interval=60.0,
            performance_history_size=5,
            animations_enabled=False,
            animation_duration=0,
            scan_interval_multiplier=3.0,
            template_cache_size=2,
            enable_debug_images=False,
            max_worker_threads=1
        )
    }
    
    def __init__(self):
        self._logger = get_logger()
        self._current_profile = None
        self._auto_detect_enabled = True
    
    def get_system_performance_level(self) -> str:
        """检测系统性能级别"""
        try:
            # 获取系统信息
            cpu_count = psutil.cpu_count()
            memory_gb = psutil.virtual_memory().total / (1024**3)
            cpu_freq = psutil.cpu_freq()
            
            # 简单的性能评估
            performance_score = 0
            
            # CPU核心数评分
            if cpu_count >= 8:
                performance_score += 3
            elif cpu_count >= 4:
                performance_score += 2
            else:
                performance_score += 1
            
            # 内存评分
            if memory_gb >= 16:
                performance_score += 3
            elif memory_gb >= 8:
                performance_score += 2
            else:
                performance_score += 1
            
            # CPU频率评分
            if cpu_freq and cpu_freq.max >= 3000:
                performance_score += 2
            elif cpu_freq and cpu_freq.max >= 2000:
                performance_score += 1
            
            # 根据评分确定性能级别
            if performance_score >= 7:
                return 'high_performance'
            elif performance_score >= 4:
                return 'balanced'
            else:
                return 'low_resource'
                
        except Exception as e:
            self._logger.warning(f"检测系统性能失败: {e}")
            return 'balanced'  # 默认返回平衡模式
    
    def get_current_profile(self) -> PerformanceProfile:
        """获取当前性能配置档案"""
        if self._current_profile is None:
            if self._auto_detect_enabled:
                level = self.get_system_performance_level()
                self._current_profile = self.PROFILES[level]
                self._logger.info(f"自动检测到系统性能级别: {level}")
            else:
                self._current_profile = self.PROFILES['balanced']
        
        return self._current_profile
    
    def set_profile(self, profile_name: str):
        """设置性能配置档案"""
        if profile_name in self.PROFILES:
            self._current_profile = self.PROFILES[profile_name]
            self._auto_detect_enabled = False
            self._logger.info(f"切换到性能档案: {profile_name}")
        else:
            self._logger.warning(f"未知的性能档案: {profile_name}")
    
    def enable_auto_detect(self, enabled: bool = True):
        """启用/禁用自动检测"""
        self._auto_detect_enabled = enabled
        if enabled:
            self._current_profile = None  # 重置，下次获取时重新检测
    
    def apply_profile_to_config(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """将性能档案应用到配置字典"""
        profile = self.get_current_profile()
        
        # 应用扫描间隔调整
        if 'interval_ms' in config_dict:
            config_dict['interval_ms'] = int(
                config_dict['interval_ms'] * profile.scan_interval_multiplier
            )
        
        # 应用调试图像设置
        config_dict['save_debug_images'] = profile.enable_debug_images
        
        return config_dict
    
    def get_ui_settings(self) -> Dict[str, Any]:
        """获取UI相关设置"""
        profile = self.get_current_profile()
        return {
            'status_update_interval': profile.status_update_interval,
            'tooltip_update_interval': profile.tooltip_update_interval,
            'ui_batch_delay': profile.ui_batch_delay,
            'animations_enabled': profile.animations_enabled,
            'animation_duration': profile.animation_duration
        }
    
    def get_monitor_settings(self) -> Dict[str, Any]:
        """获取监控相关设置"""
        profile = self.get_current_profile()
        return {
            'monitor_interval': profile.performance_monitor_interval,
            'history_size': profile.performance_history_size
        }
    
    def get_optimization_settings(self) -> Dict[str, Any]:
        """获取优化相关设置"""
        profile = self.get_current_profile()
        return {
            'template_cache_size': profile.template_cache_size,
            'max_worker_threads': profile.max_worker_threads
        }


# 全局实例
_performance_config_manager = PerformanceConfigManager()


def get_performance_config() -> PerformanceConfigManager:
    """获取性能配置管理器实例"""
    return _performance_config_manager


def apply_performance_optimizations():
    """应用性能优化设置到各个模块"""
    config_manager = get_performance_config()
    ui_settings = config_manager.get_ui_settings()
    
    # 应用UI设置
    try:
        from auto_approve.ui_enhancements import UIEnhancementManager
        UIEnhancementManager.set_animations_enabled(ui_settings['animations_enabled'])
    except ImportError:
        pass
    
    # 应用其他设置...
    logger = get_logger()
    logger.info(f"已应用性能优化设置: {config_manager.get_current_profile().name}")

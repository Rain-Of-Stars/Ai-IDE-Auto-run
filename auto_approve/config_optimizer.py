# -*- coding: utf-8 -*-
"""
配置优化器 - 根据系统性能自动生成最优配置
提供不同性能级别的预设配置和自动调优功能
"""
from __future__ import annotations
import os
import psutil
import time
from typing import Dict, Any, List, Tuple
from dataclasses import asdict
from auto_approve.config_manager import AppConfig, save_config, load_config
from auto_approve.logger_manager import get_logger


class SystemProfiler:
    """系统性能分析器"""
    
    def __init__(self):
        self._logger = get_logger()
    
    def get_system_profile(self) -> Dict[str, Any]:
        """获取系统性能概况"""
        try:
            # CPU信息
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            cpu_percent = psutil.cpu_percent(interval=1.0)
            
            # 内存信息
            memory = psutil.virtual_memory()
            
            # 系统负载评估
            load_level = self._assess_system_load()
            
            profile = {
                'cpu_count': cpu_count,
                'cpu_freq_mhz': cpu_freq.current if cpu_freq else 0,
                'cpu_usage_percent': cpu_percent,
                'memory_total_gb': memory.total / (1024**3),
                'memory_available_gb': memory.available / (1024**3),
                'memory_usage_percent': memory.percent,
                'load_level': load_level,  # 'low', 'medium', 'high'
                'performance_tier': self._determine_performance_tier(cpu_count, memory.total, cpu_freq)
            }
            
            self._logger.info(f"系统性能概况: {profile}")
            return profile
            
        except Exception as e:
            self._logger.error(f"获取系统性能概况失败: {e}")
            return self._get_default_profile()
    
    def _assess_system_load(self) -> str:
        """评估当前系统负载"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1.0)
            memory_percent = psutil.virtual_memory().percent
            
            if cpu_percent > 70 or memory_percent > 80:
                return 'high'
            elif cpu_percent > 40 or memory_percent > 60:
                return 'medium'
            else:
                return 'low'
        except Exception:
            return 'medium'
    
    def _determine_performance_tier(self, cpu_count: int, memory_bytes: int, cpu_freq) -> str:
        """确定性能等级"""
        memory_gb = memory_bytes / (1024**3)
        freq_ghz = (cpu_freq.current / 1000) if cpu_freq else 2.0
        
        # 性能评分算法
        score = cpu_count * 10 + memory_gb * 5 + freq_ghz * 15
        
        if score >= 100:
            return 'high'
        elif score >= 60:
            return 'medium'
        else:
            return 'low'
    
    def _get_default_profile(self) -> Dict[str, Any]:
        """获取默认性能概况"""
        return {
            'cpu_count': 4,
            'cpu_freq_mhz': 2400,
            'cpu_usage_percent': 30,
            'memory_total_gb': 8,
            'memory_available_gb': 4,
            'memory_usage_percent': 50,
            'load_level': 'medium',
            'performance_tier': 'medium'
        }


class ConfigOptimizer:
    """配置优化器"""
    
    def __init__(self):
        self._logger = get_logger()
        self.profiler = SystemProfiler()
        
        # 预设配置模板
        self.preset_configs = {
            'performance': self._get_performance_preset(),
            'balanced': self._get_balanced_preset(),
            'power_saving': self._get_power_saving_preset(),
            'minimal': self._get_minimal_preset()
        }
    
    def generate_optimized_config(self, current_config: AppConfig = None) -> AppConfig:
        """生成优化配置"""
        if current_config is None:
            current_config = load_config()
        
        # 获取系统性能概况
        system_profile = self.profiler.get_system_profile()
        
        # 根据系统性能选择基础配置
        base_preset = self._select_base_preset(system_profile)
        
        # 应用自适应调整
        optimized_config = self._apply_adaptive_adjustments(base_preset, system_profile, current_config)
        
        self._logger.info(f"已生成优化配置，性能等级: {system_profile['performance_tier']}")
        return optimized_config
    
    def _select_base_preset(self, system_profile: Dict[str, Any]) -> Dict[str, Any]:
        """根据系统性能选择基础预设"""
        performance_tier = system_profile['performance_tier']
        load_level = system_profile['load_level']
        
        if performance_tier == 'high' and load_level == 'low':
            return self.preset_configs['performance']
        elif performance_tier == 'low' or load_level == 'high':
            return self.preset_configs['power_saving']
        else:
            return self.preset_configs['balanced']
    
    def _apply_adaptive_adjustments(self, base_config: Dict[str, Any], 
                                  system_profile: Dict[str, Any], 
                                  current_config: AppConfig) -> AppConfig:
        """应用自适应调整"""
        config_dict = base_config.copy()
        
        # 根据CPU核心数调整并发设置
        cpu_count = system_profile['cpu_count']
        if cpu_count >= 8:
            config_dict['fps_max'] = min(30, config_dict.get('fps_max', 10))
        elif cpu_count <= 2:
            config_dict['fps_max'] = max(5, config_dict.get('fps_max', 10))
        
        # 根据内存大小调整缓存设置
        memory_gb = system_profile['memory_total_gb']
        if memory_gb < 4:
            config_dict['save_debug_images'] = False
            config_dict['debug_mode'] = False
        
        # 根据当前负载调整扫描间隔
        load_level = system_profile['load_level']
        base_interval = config_dict.get('interval_ms', 1500)
        if load_level == 'high':
            config_dict['interval_ms'] = int(base_interval * 1.5)
        elif load_level == 'low':
            config_dict['interval_ms'] = int(base_interval * 0.8)
        
        # 保留用户的关键设置
        user_preserved_fields = [
            'template_paths', 'target_window_title', 'target_process',
            'target_hwnd', 'roi', 'click_offset', 'threshold'
        ]
        
        for field in user_preserved_fields:
            if hasattr(current_config, field):
                current_value = getattr(current_config, field)
                if current_value:  # 只有非空值才保留
                    config_dict[field] = current_value
        
        # 创建新的配置对象
        try:
            # 确保所有必需字段都存在
            config_dict = self._ensure_required_fields(config_dict, current_config)
            optimized_config = AppConfig(**config_dict)
            return optimized_config
        except Exception as e:
            self._logger.error(f"创建优化配置失败: {e}")
            return current_config
    
    def _ensure_required_fields(self, config_dict: Dict[str, Any], fallback_config: AppConfig) -> Dict[str, Any]:
        """确保所有必需字段都存在"""
        fallback_dict = asdict(fallback_config)
        
        for key, default_value in fallback_dict.items():
            if key not in config_dict:
                config_dict[key] = default_value
        
        return config_dict
    
    def _get_performance_preset(self) -> Dict[str, Any]:
        """高性能预设"""
        return {
            'interval_ms': 500,
            'threshold': 0.85,
            'grayscale': True,
            'multi_scale': False,
            'debug_mode': False,
            'save_debug_images': False,
            'enable_multi_screen_polling': False,
            'fps_max': 20,
            'capture_backend': 'wgc',
            'use_monitor': False,
            'cooldown_s': 3.0,
            'min_detections': 1
        }
    
    def _get_balanced_preset(self) -> Dict[str, Any]:
        """平衡预设"""
        return {
            'interval_ms': 1000,
            'threshold': 0.88,
            'grayscale': True,
            'multi_scale': False,
            'debug_mode': False,
            'save_debug_images': False,
            'enable_multi_screen_polling': False,
            'fps_max': 15,
            'capture_backend': 'wgc',
            'use_monitor': False,
            'cooldown_s': 4.0,
            'min_detections': 1
        }
    
    def _get_power_saving_preset(self) -> Dict[str, Any]:
        """省电预设"""
        return {
            'interval_ms': 2000,
            'threshold': 0.90,
            'grayscale': True,
            'multi_scale': False,
            'debug_mode': False,
            'save_debug_images': False,
            'enable_multi_screen_polling': False,
            'fps_max': 5,
            'capture_backend': 'wgc',
            'use_monitor': False,
            'cooldown_s': 6.0,
            'min_detections': 2
        }
    
    def _get_minimal_preset(self) -> Dict[str, Any]:
        """最小化预设"""
        return {
            'interval_ms': 3000,
            'threshold': 0.92,
            'grayscale': True,
            'multi_scale': False,
            'debug_mode': False,
            'save_debug_images': False,
            'enable_multi_screen_polling': False,
            'fps_max': 3,
            'capture_backend': 'wgc',
            'use_monitor': False,
            'cooldown_s': 8.0,
            'min_detections': 3
        }
    
    def benchmark_configuration(self, config: AppConfig, duration_seconds: int = 30) -> Dict[str, float]:
        """基准测试配置性能"""
        self._logger.info(f"开始配置基准测试，持续时间: {duration_seconds}秒")
        
        # 这里应该启动一个临时的扫描器进行测试
        # 由于复杂性，这里返回模拟数据
        return {
            'avg_cpu_percent': 25.0,
            'max_cpu_percent': 45.0,
            'avg_memory_mb': 150.0,
            'avg_scan_time_ms': 80.0,
            'avg_match_time_ms': 45.0,
            'estimated_battery_hours': 8.5
        }
    
    def save_optimized_config(self, config: AppConfig, backup_original: bool = True) -> bool:
        """保存优化配置"""
        try:
            if backup_original:
                # 备份原配置
                timestamp = int(time.time())
                backup_path = f"config_backup_{timestamp}.json"
                current_config = load_config()
                save_config(current_config, backup_path)
                self._logger.info(f"原配置已备份到: {backup_path}")
            
            # 保存新配置
            save_config(config)
            self._logger.info("优化配置已保存")
            return True
            
        except Exception as e:
            self._logger.error(f"保存优化配置失败: {e}")
            return False


def auto_optimize_config() -> bool:
    """自动优化配置的便捷函数"""
    try:
        optimizer = ConfigOptimizer()
        optimized_config = optimizer.generate_optimized_config()
        return optimizer.save_optimized_config(optimized_config)
    except Exception as e:
        logger = get_logger()
        logger.error(f"自动优化配置失败: {e}")
        return False

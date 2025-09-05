# -*- coding: utf-8 -*-
"""
内存配置管理器 - 避免频繁磁盘IO的配置缓存系统

主要功能：
1. 配置数据的内存缓存
2. 智能的配置变更检测
3. 批量配置更新和延迟写入
4. 配置版本管理和回滚
"""
from __future__ import annotations
import os
import json
import time
import hashlib
import threading
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
import copy

from auto_approve.logger_manager import get_logger


@dataclass
class ConfigSnapshot:
    """配置快照"""
    data: Dict[str, Any]
    timestamp: float
    file_hash: str
    version: int


class MemoryConfigManager:
    """内存配置管理器 - 减少磁盘IO的配置系统"""
    
    def __init__(self, auto_save_interval: float = 30.0):
        self._logger = get_logger()
        self._configs: Dict[str, ConfigSnapshot] = {}
        self._lock = threading.RLock()
        self._auto_save_interval = auto_save_interval
        self._pending_changes: Dict[str, Dict[str, Any]] = {}
        self._change_callbacks: Dict[str, list] = {}
        self._version_counter = 0
        
        # 启动自动保存线程
        self._auto_save_thread = threading.Thread(target=self._auto_save_worker, daemon=True)
        self._auto_save_thread.start()
        
    def load_config(self, config_path: str, default_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        加载配置文件到内存
        
        Args:
            config_path: 配置文件路径
            default_config: 默认配置
            
        Returns:
            配置数据字典
        """
        config_path = os.path.abspath(config_path)
        
        with self._lock:
            # 检查是否已缓存且未过期
            if config_path in self._configs:
                cached = self._configs[config_path]
                
                # 检查文件是否有变更
                if os.path.exists(config_path):
                    current_hash = self._calculate_file_hash(config_path)
                    if current_hash == cached.file_hash:
                        # 文件未变更，返回缓存数据
                        self._logger.debug(f"从内存缓存加载配置: {config_path}")
                        return copy.deepcopy(cached.data)
            
            # 从磁盘加载配置
            try:
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    file_hash = self._calculate_file_hash(config_path)
                else:
                    # 文件不存在，使用默认配置
                    config_data = default_config or {}
                    file_hash = ""
                
                # 缓存配置
                self._version_counter += 1
                snapshot = ConfigSnapshot(
                    data=copy.deepcopy(config_data),
                    timestamp=time.time(),
                    file_hash=file_hash,
                    version=self._version_counter
                )
                self._configs[config_path] = snapshot
                
                self._logger.info(f"配置已加载到内存: {config_path} (版本 {self._version_counter})")
                return copy.deepcopy(config_data)
                
            except Exception as e:
                self._logger.error(f"加载配置文件失败 {config_path}: {e}")
                return default_config or {}
    
    def get_config(self, config_path: str, key: Optional[str] = None, default: Any = None) -> Any:
        """
        获取配置值（纯内存操作）
        
        Args:
            config_path: 配置文件路径
            key: 配置键，None表示获取整个配置
            default: 默认值
            
        Returns:
            配置值
        """
        config_path = os.path.abspath(config_path)
        
        with self._lock:
            if config_path not in self._configs:
                # 配置未加载，先加载
                self.load_config(config_path)
            
            if config_path in self._configs:
                config_data = self._configs[config_path].data
                
                # 应用待保存的变更
                if config_path in self._pending_changes:
                    config_data = copy.deepcopy(config_data)
                    config_data.update(self._pending_changes[config_path])
                
                if key is None:
                    return copy.deepcopy(config_data)
                else:
                    return config_data.get(key, default)
            
            return default
    
    def set_config(self, config_path: str, key: str, value: Any, immediate_save: bool = False) -> bool:
        """
        设置配置值（内存操作，延迟写入）
        
        Args:
            config_path: 配置文件路径
            key: 配置键
            value: 配置值
            immediate_save: 是否立即保存到磁盘
            
        Returns:
            是否成功
        """
        config_path = os.path.abspath(config_path)
        
        try:
            with self._lock:
                # 确保配置已加载
                if config_path not in self._configs:
                    self.load_config(config_path)
                
                # 记录待保存的变更
                if config_path not in self._pending_changes:
                    self._pending_changes[config_path] = {}
                
                old_value = self._pending_changes[config_path].get(key)
                self._pending_changes[config_path][key] = value
                
                # 触发变更回调
                self._trigger_change_callbacks(config_path, key, old_value, value)
                
                if immediate_save:
                    return self._save_config_to_disk(config_path)
                
                self._logger.debug(f"配置变更已缓存: {config_path}[{key}] = {value}")
                return True
                
        except Exception as e:
            self._logger.error(f"设置配置失败 {config_path}[{key}]: {e}")
            return False
    
    def update_config(self, config_path: str, updates: Dict[str, Any], immediate_save: bool = False) -> bool:
        """
        批量更新配置
        
        Args:
            config_path: 配置文件路径
            updates: 更新的配置字典
            immediate_save: 是否立即保存
            
        Returns:
            是否成功
        """
        config_path = os.path.abspath(config_path)
        
        try:
            with self._lock:
                # 确保配置已加载
                if config_path not in self._configs:
                    self.load_config(config_path)
                
                # 记录待保存的变更
                if config_path not in self._pending_changes:
                    self._pending_changes[config_path] = {}
                
                for key, value in updates.items():
                    old_value = self._pending_changes[config_path].get(key)
                    self._pending_changes[config_path][key] = value
                    self._trigger_change_callbacks(config_path, key, old_value, value)
                
                if immediate_save:
                    return self._save_config_to_disk(config_path)
                
                self._logger.debug(f"批量配置变更已缓存: {config_path} ({len(updates)}项)")
                return True
                
        except Exception as e:
            self._logger.error(f"批量更新配置失败 {config_path}: {e}")
            return False
    
    def save_config(self, config_path: str) -> bool:
        """立即保存配置到磁盘"""
        config_path = os.path.abspath(config_path)
        return self._save_config_to_disk(config_path)
    
    def _save_config_to_disk(self, config_path: str) -> bool:
        """内部方法：保存配置到磁盘"""
        try:
            with self._lock:
                if config_path not in self._configs:
                    return False
                
                # 合并待保存的变更
                config_data = copy.deepcopy(self._configs[config_path].data)
                if config_path in self._pending_changes:
                    config_data.update(self._pending_changes[config_path])
                    del self._pending_changes[config_path]
                
                # 确保目录存在
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
                
                # 写入文件
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
                
                # 更新缓存
                self._version_counter += 1
                self._configs[config_path] = ConfigSnapshot(
                    data=config_data,
                    timestamp=time.time(),
                    file_hash=self._calculate_file_hash(config_path),
                    version=self._version_counter
                )
                
                self._logger.debug(f"配置已保存到磁盘: {config_path} (版本 {self._version_counter})")
                return True
                
        except Exception as e:
            self._logger.error(f"保存配置到磁盘失败 {config_path}: {e}")
            return False
    
    def _auto_save_worker(self):
        """自动保存工作线程"""
        while True:
            try:
                time.sleep(self._auto_save_interval)
                
                with self._lock:
                    # 保存所有有待保存变更的配置
                    for config_path in list(self._pending_changes.keys()):
                        if self._pending_changes[config_path]:  # 有变更
                            self._save_config_to_disk(config_path)
                            
            except Exception as e:
                self._logger.error(f"自动保存配置异常: {e}")
    
    def register_change_callback(self, config_path: str, callback: Callable[[str, Any, Any], None]):
        """注册配置变更回调"""
        config_path = os.path.abspath(config_path)
        if config_path not in self._change_callbacks:
            self._change_callbacks[config_path] = []
        self._change_callbacks[config_path].append(callback)
    
    def _trigger_change_callbacks(self, config_path: str, key: str, old_value: Any, new_value: Any):
        """触发配置变更回调"""
        if config_path in self._change_callbacks:
            for callback in self._change_callbacks[config_path]:
                try:
                    callback(key, old_value, new_value)
                except Exception as e:
                    self._logger.error(f"配置变更回调异常: {e}")
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件哈希值"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            return {
                'cached_configs': len(self._configs),
                'pending_changes': len(self._pending_changes),
                'total_pending_items': sum(len(changes) for changes in self._pending_changes.values()),
                'auto_save_interval': self._auto_save_interval,
                'current_version': self._version_counter
            }
    
    def clear_cache(self):
        """清空缓存"""
        with self._lock:
            self._configs.clear()
            self._pending_changes.clear()
            self._change_callbacks.clear()
        self._logger.info("配置缓存已清空")


# 全局实例
_config_manager: Optional[MemoryConfigManager] = None


def get_config_manager() -> MemoryConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = MemoryConfigManager()
    return _config_manager

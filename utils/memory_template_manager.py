# -*- coding: utf-8 -*-
"""
内存模板管理器 - 避免磁盘IO的模板缓存系统

主要功能：
1. 启动时一次性加载所有模板到内存
2. 提供高效的内存模板访问接口
3. 支持模板热更新和缓存失效
4. 内存使用监控和优化
"""
from __future__ import annotations
import os
import time
import hashlib
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import numpy as np
import cv2
from dataclasses import dataclass
from threading import RLock

from auto_approve.logger_manager import get_logger


@dataclass
class TemplateInfo:
    """模板信息"""
    path: str
    data: np.ndarray
    size: Tuple[int, int]  # (width, height)
    file_hash: str
    load_time: float
    last_access: float
    access_count: int


class MemoryTemplateManager:
    """内存模板管理器 - 完全避免磁盘IO的模板系统"""
    
    def __init__(self):
        self._logger = get_logger()
        self._templates: Dict[str, TemplateInfo] = {}
        self._lock = RLock()
        self._total_memory_usage = 0
        self._max_memory_mb = 100  # 最大内存使用限制（MB）
        self._cache_hit_count = 0
        self._cache_miss_count = 0
        
    def load_templates(self, template_paths: List[str], force_reload: bool = False) -> int:
        """
        批量加载模板到内存
        
        Args:
            template_paths: 模板文件路径列表
            force_reload: 是否强制重新加载
            
        Returns:
            成功加载的模板数量
        """
        loaded_count = 0
        
        with self._lock:
            for path in template_paths:
                try:
                    if self._load_single_template(path, force_reload):
                        loaded_count += 1
                except Exception as e:
                    self._logger.error(f"加载模板失败 {path}: {e}")
        
        self._logger.info(f"模板加载完成: {loaded_count}/{len(template_paths)} 个模板")
        self._log_memory_usage()
        return loaded_count
    
    def _load_single_template(self, path: str, force_reload: bool = False) -> bool:
        """加载单个模板"""
        if not os.path.exists(path):
            self._logger.warning(f"模板文件不存在: {path}")
            return False
        
        # 计算文件哈希
        file_hash = self._calculate_file_hash(path)
        
        # 检查是否需要重新加载
        if not force_reload and path in self._templates:
            existing = self._templates[path]
            if existing.file_hash == file_hash:
                # 更新访问时间
                existing.last_access = time.time()
                existing.access_count += 1
                self._cache_hit_count += 1
                return True
        
        # 加载图像数据
        try:
            # 使用cv2.imdecode处理中文路径
            img_data = np.fromfile(path, dtype=np.uint8)
            template = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
            
            if template is None:
                self._logger.error(f"无法解码模板图像: {path}")
                return False
            
            h, w = template.shape[:2]
            memory_size = template.nbytes
            
            # 检查内存限制
            if self._total_memory_usage + memory_size > self._max_memory_mb * 1024 * 1024:
                self._cleanup_old_templates()
                
                # 再次检查
                if self._total_memory_usage + memory_size > self._max_memory_mb * 1024 * 1024:
                    self._logger.warning(f"内存不足，跳过加载模板: {path}")
                    return False
            
            # 创建模板信息
            template_info = TemplateInfo(
                path=path,
                data=template.copy(),  # 确保数据独立
                size=(w, h),
                file_hash=file_hash,
                load_time=time.time(),
                last_access=time.time(),
                access_count=1
            )
            
            # 更新缓存
            if path in self._templates:
                old_size = self._templates[path].data.nbytes
                self._total_memory_usage -= old_size
            
            self._templates[path] = template_info
            self._total_memory_usage += memory_size
            self._cache_miss_count += 1
            
            self._logger.debug(f"模板加载成功: {path} ({w}x{h}, {memory_size/1024:.1f}KB)")
            return True
            
        except Exception as e:
            self._logger.error(f"加载模板异常 {path}: {e}")
            return False
    
    def get_templates(self, template_paths: List[str]) -> List[Tuple[np.ndarray, Tuple[int, int]]]:
        """
        获取模板数据（纯内存操作）
        
        Args:
            template_paths: 模板路径列表
            
        Returns:
            模板数据列表 [(template_data, (width, height)), ...]
        """
        templates = []
        
        with self._lock:
            for path in template_paths:
                if path in self._templates:
                    template_info = self._templates[path]
                    # 更新访问统计
                    template_info.last_access = time.time()
                    template_info.access_count += 1
                    self._cache_hit_count += 1
                    
                    # 返回数据副本以避免意外修改
                    templates.append((template_info.data.copy(), template_info.size))
                else:
                    # 缓存未命中，尝试即时加载
                    if self._load_single_template(path):
                        template_info = self._templates[path]
                        templates.append((template_info.data.copy(), template_info.size))
                    else:
                        self._logger.warning(f"无法获取模板: {path}")
        
        return templates
    
    def _calculate_file_hash(self, path: str) -> str:
        """计算文件哈希值"""
        try:
            with open(path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
    
    def _cleanup_old_templates(self):
        """清理旧的模板以释放内存"""
        if not self._templates:
            return
        
        # 按最后访问时间排序，删除最旧的模板
        sorted_templates = sorted(
            self._templates.items(),
            key=lambda x: x[1].last_access
        )
        
        # 删除最旧的25%模板
        cleanup_count = max(1, len(sorted_templates) // 4)
        
        for i in range(cleanup_count):
            path, template_info = sorted_templates[i]
            self._total_memory_usage -= template_info.data.nbytes
            del self._templates[path]
            self._logger.debug(f"清理旧模板: {path}")
    
    def _log_memory_usage(self):
        """记录内存使用情况"""
        memory_mb = self._total_memory_usage / (1024 * 1024)
        hit_rate = self._cache_hit_count / max(1, self._cache_hit_count + self._cache_miss_count) * 100
        
        self._logger.info(
            f"模板缓存状态: {len(self._templates)}个模板, "
            f"{memory_mb:.1f}MB内存, 命中率{hit_rate:.1f}%"
        )
    
    def clear_cache(self):
        """清空缓存"""
        with self._lock:
            self._templates.clear()
            self._total_memory_usage = 0
            self._cache_hit_count = 0
            self._cache_miss_count = 0
        self._logger.info("模板缓存已清空")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            total_requests = self._cache_hit_count + self._cache_miss_count
            hit_rate = self._cache_hit_count / max(1, total_requests) * 100
            
            return {
                'template_count': len(self._templates),
                'memory_usage_mb': self._total_memory_usage / (1024 * 1024),
                'cache_hit_count': self._cache_hit_count,
                'cache_miss_count': self._cache_miss_count,
                'hit_rate_percent': hit_rate,
                'max_memory_mb': self._max_memory_mb
            }


# 全局实例
_template_manager: Optional[MemoryTemplateManager] = None


def get_template_manager() -> MemoryTemplateManager:
    """获取全局模板管理器实例"""
    global _template_manager
    if _template_manager is None:
        _template_manager = MemoryTemplateManager()
    return _template_manager

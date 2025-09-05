# -*- coding: utf-8 -*-
"""
共享帧缓存系统

实现预览图和检测图的内存共享，避免重复捕获和处理。
支持一次捕获，多次使用的模式。
"""

import threading
import time
import weakref
from typing import Optional, Dict, Any, Callable
import numpy as np

from auto_approve.logger_manager import get_logger


class SharedFrameCache:
    """
    共享帧缓存系统
    
    特性：
    - 一次捕获，多处使用
    - 内存共享，避免重复拷贝
    - 自动生命周期管理
    - 线程安全
    """
    
    def __init__(self):
        self._logger = get_logger()
        self._lock = threading.RLock()
        
        # 当前缓存的帧数据
        self._cached_frame: Optional[np.ndarray] = None
        self._frame_timestamp: float = 0.0
        self._frame_id: str = ""
        
        # 引用计数和使用者跟踪
        self._reference_count = 0
        self._users: Dict[str, Any] = {}  # 使用者ID -> 使用者信息
        
        # 缓存配置
        self._max_cache_age = 5.0  # 最大缓存时间（秒）
        self._auto_cleanup = True
        
        # 统计信息
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_captures = 0
        
    def cache_frame(self, frame: np.ndarray, frame_id: str = None) -> str:
        """
        缓存一帧图像
        
        Args:
            frame: BGR图像数据
            frame_id: 帧ID，如果为None则自动生成
            
        Returns:
            str: 帧ID
        """
        with self._lock:
            if frame_id is None:
                frame_id = f"frame_{int(time.time() * 1000000)}"
            
            # 清理旧缓存
            self._cleanup_old_cache()
            
            # 缓存新帧
            self._cached_frame = frame.copy() if frame is not None else None
            self._frame_timestamp = time.time()
            self._frame_id = frame_id
            self._reference_count = 0
            self._users.clear()
            self._total_captures += 1
            
            self._logger.debug(f"缓存新帧: {frame_id}, 尺寸: {frame.shape if frame is not None else 'None'}")
            return frame_id
    
    def get_frame(self, user_id: str, frame_id: str = None) -> Optional[np.ndarray]:
        """
        获取缓存的帧
        
        Args:
            user_id: 使用者ID（如"preview", "detection"等）
            frame_id: 指定的帧ID，如果为None则返回最新帧
            
        Returns:
            np.ndarray: BGR图像数据，如果缓存无效则返回None
        """
        with self._lock:
            # 检查缓存有效性
            if not self._is_cache_valid(frame_id):
                self._cache_misses += 1
                return None
            
            # 注册使用者
            self._users[user_id] = {
                'access_time': time.time(),
                'access_count': self._users.get(user_id, {}).get('access_count', 0) + 1
            }
            self._reference_count = len(self._users)
            self._cache_hits += 1
            
            self._logger.debug(f"用户 {user_id} 访问缓存帧 {self._frame_id}, 当前用户数: {self._reference_count}")
            
            # 返回帧的视图（避免拷贝）
            return self._cached_frame
    
    def release_user(self, user_id: str) -> None:
        """
        释放使用者引用
        
        Args:
            user_id: 使用者ID
        """
        with self._lock:
            if user_id in self._users:
                del self._users[user_id]
                self._reference_count = len(self._users)
                
                self._logger.debug(f"用户 {user_id} 释放引用, 剩余用户数: {self._reference_count}")
                
                # 如果没有用户了，考虑清理缓存
                if self._reference_count == 0 and self._auto_cleanup:
                    self._cleanup_cache()
    
    def force_cleanup(self) -> None:
        """强制清理缓存"""
        with self._lock:
            self._cleanup_cache()
    
    def _is_cache_valid(self, frame_id: str = None) -> bool:
        """检查缓存是否有效"""
        if self._cached_frame is None:
            return False
        
        # 检查帧ID匹配
        if frame_id is not None and frame_id != self._frame_id:
            return False
        
        # 检查缓存年龄
        age = time.time() - self._frame_timestamp
        if age > self._max_cache_age:
            self._logger.debug(f"缓存过期: {age:.2f}s > {self._max_cache_age}s")
            return False
        
        return True
    
    def _cleanup_old_cache(self) -> None:
        """清理过期缓存"""
        if not self._is_cache_valid():
            self._cleanup_cache()
    
    def _cleanup_cache(self) -> None:
        """清理缓存"""
        if self._cached_frame is not None:
            self._logger.debug(f"清理缓存帧: {self._frame_id}")
            self._cached_frame = None
            self._frame_timestamp = 0.0
            self._frame_id = ""
            self._reference_count = 0
            self._users.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            hit_rate = self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0
            
            return {
                'cache_hits': self._cache_hits,
                'cache_misses': self._cache_misses,
                'hit_rate': hit_rate,
                'total_captures': self._total_captures,
                'current_users': len(self._users),
                'current_frame_id': self._frame_id,
                'cache_age': time.time() - self._frame_timestamp if self._frame_timestamp > 0 else 0,
                'users': list(self._users.keys())
            }
    
    def configure(self, max_cache_age: float = None, auto_cleanup: bool = None) -> None:
        """配置缓存参数"""
        with self._lock:
            if max_cache_age is not None:
                self._max_cache_age = max_cache_age
            if auto_cleanup is not None:
                self._auto_cleanup = auto_cleanup


# 全局共享缓存实例
_global_frame_cache: Optional[SharedFrameCache] = None
_cache_lock = threading.Lock()


def get_shared_frame_cache() -> SharedFrameCache:
    """获取全局共享帧缓存实例"""
    global _global_frame_cache
    
    with _cache_lock:
        if _global_frame_cache is None:
            _global_frame_cache = SharedFrameCache()
        return _global_frame_cache


def cleanup_shared_frame_cache() -> None:
    """清理全局共享帧缓存"""
    global _global_frame_cache
    
    with _cache_lock:
        if _global_frame_cache is not None:
            _global_frame_cache.force_cleanup()
            _global_frame_cache = None

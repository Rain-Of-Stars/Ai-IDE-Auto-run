# -*- coding: utf-8 -*-
"""
全局共享帧缓存管理器

提供应用程序级别的共享帧缓存管理，包括：
- 全局缓存状态监控
- 用户会话管理
- 资源清理和优化
- 统计信息收集
"""

import threading
import time
import atexit
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .shared_frame_cache import get_shared_frame_cache, cleanup_shared_frame_cache
from auto_approve.logger_manager import get_logger


@dataclass
class UserSession:
    """用户会话信息"""
    user_id: str
    session_type: str  # "preview", "detection", "test", etc.
    start_time: float
    last_access_time: float
    access_count: int
    hwnd: Optional[int] = None
    description: str = ""


class GlobalCacheManager:
    """
    全局共享帧缓存管理器
    
    功能：
    - 跟踪所有活跃的用户会话
    - 监控缓存使用情况
    - 自动清理过期会话
    - 提供统计和诊断信息
    """
    
    def __init__(self):
        self._logger = get_logger()
        self._lock = threading.RLock()
        
        # 用户会话跟踪
        self._active_sessions: Dict[str, UserSession] = {}
        
        # 配置参数
        self._session_timeout = 300.0  # 5分钟会话超时
        self._cleanup_interval = 60.0  # 1分钟清理间隔
        
        # 清理定时器
        self._cleanup_timer: Optional[threading.Timer] = None
        self._start_cleanup_timer()
        
        # 统计信息
        self._total_sessions_created = 0
        self._total_sessions_expired = 0
        
        # 注册退出清理
        atexit.register(self.cleanup_all)
    
    def register_user(self, user_id: str, session_type: str, hwnd: Optional[int] = None, description: str = "") -> None:
        """
        注册新用户会话
        
        Args:
            user_id: 用户ID
            session_type: 会话类型（preview, detection, test等）
            hwnd: 关联的窗口句柄（可选）
            description: 会话描述（可选）
        """
        with self._lock:
            current_time = time.time()
            
            session = UserSession(
                user_id=user_id,
                session_type=session_type,
                start_time=current_time,
                last_access_time=current_time,
                access_count=0,
                hwnd=hwnd,
                description=description
            )
            
            self._active_sessions[user_id] = session
            self._total_sessions_created += 1
            
            self._logger.debug(f"注册用户会话: {user_id} ({session_type})")
    
    def update_user_access(self, user_id: str) -> None:
        """
        更新用户访问时间
        
        Args:
            user_id: 用户ID
        """
        with self._lock:
            if user_id in self._active_sessions:
                session = self._active_sessions[user_id]
                session.last_access_time = time.time()
                session.access_count += 1
    
    def unregister_user(self, user_id: str) -> None:
        """
        注销用户会话
        
        Args:
            user_id: 用户ID
        """
        with self._lock:
            if user_id in self._active_sessions:
                session = self._active_sessions[user_id]
                del self._active_sessions[user_id]
                
                # 释放共享帧缓存引用
                cache = get_shared_frame_cache()
                cache.release_user(user_id)
                
                self._logger.debug(f"注销用户会话: {user_id} ({session.session_type})")
    
    def cleanup_expired_sessions(self) -> int:
        """
        清理过期会话
        
        Returns:
            int: 清理的会话数量
        """
        with self._lock:
            current_time = time.time()
            expired_users = []
            
            for user_id, session in self._active_sessions.items():
                if current_time - session.last_access_time > self._session_timeout:
                    expired_users.append(user_id)
            
            for user_id in expired_users:
                self.unregister_user(user_id)
                self._total_sessions_expired += 1
            
            if expired_users:
                self._logger.info(f"清理了 {len(expired_users)} 个过期会话")
            
            return len(expired_users)
    
    def get_active_sessions(self) -> List[UserSession]:
        """获取所有活跃会话"""
        with self._lock:
            return list(self._active_sessions.values())
    
    def get_session_by_type(self, session_type: str) -> List[UserSession]:
        """根据类型获取会话"""
        with self._lock:
            return [session for session in self._active_sessions.values() 
                   if session.session_type == session_type]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            cache = get_shared_frame_cache()
            cache_stats = cache.get_stats()
            
            session_types = {}
            for session in self._active_sessions.values():
                session_types[session.session_type] = session_types.get(session.session_type, 0) + 1
            
            return {
                'active_sessions': len(self._active_sessions),
                'session_types': session_types,
                'total_sessions_created': self._total_sessions_created,
                'total_sessions_expired': self._total_sessions_expired,
                'cache_stats': cache_stats,
                'session_timeout': self._session_timeout,
                'cleanup_interval': self._cleanup_interval
            }
    
    def force_cleanup_all(self) -> None:
        """强制清理所有会话和缓存"""
        with self._lock:
            # 注销所有会话
            user_ids = list(self._active_sessions.keys())
            for user_id in user_ids:
                self.unregister_user(user_id)
            
            # 清理共享帧缓存
            cleanup_shared_frame_cache()
            
            self._logger.info("强制清理了所有会话和缓存")
    
    def cleanup_all(self) -> None:
        """清理所有资源（退出时调用）"""
        try:
            # 停止清理定时器
            if self._cleanup_timer:
                self._cleanup_timer.cancel()
                self._cleanup_timer = None
            
            # 清理所有会话
            self.force_cleanup_all()
            
            self._logger.info("全局缓存管理器已清理")
        except Exception as e:
            self._logger.error(f"清理全局缓存管理器失败: {e}")
    
    def _start_cleanup_timer(self) -> None:
        """启动清理定时器"""
        def cleanup_task():
            try:
                self.cleanup_expired_sessions()
            except Exception as e:
                self._logger.error(f"定时清理任务失败: {e}")
            finally:
                # 重新启动定时器
                self._start_cleanup_timer()
        
        self._cleanup_timer = threading.Timer(self._cleanup_interval, cleanup_task)
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()
    
    def configure(self, session_timeout: float = None, cleanup_interval: float = None) -> None:
        """配置管理器参数"""
        with self._lock:
            if session_timeout is not None:
                self._session_timeout = session_timeout
            if cleanup_interval is not None:
                self._cleanup_interval = cleanup_interval


# 全局实例
_global_cache_manager: Optional[GlobalCacheManager] = None
_manager_lock = threading.Lock()


def get_global_cache_manager() -> GlobalCacheManager:
    """获取全局缓存管理器实例"""
    global _global_cache_manager
    
    with _manager_lock:
        if _global_cache_manager is None:
            _global_cache_manager = GlobalCacheManager()
        return _global_cache_manager


def cleanup_global_cache_manager() -> None:
    """清理全局缓存管理器"""
    global _global_cache_manager
    
    with _manager_lock:
        if _global_cache_manager is not None:
            _global_cache_manager.cleanup_all()
            _global_cache_manager = None

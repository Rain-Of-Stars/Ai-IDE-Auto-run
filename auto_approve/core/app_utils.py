# -*- coding: utf-8 -*-
"""
应用工具模块

提供应用生命周期管理的公共函数
"""

import sys
import time
import signal
import threading
from typing import Optional, Callable, Any
from auto_approve.logger_manager import get_logger


class AppLifecycleManager:
    """应用生命周期管理器"""
    
    def __init__(self):
        self.logger = get_logger()
        self.cleanup_callbacks = []  # 清理回调函数列表
        self.shutdown_in_progress = False
        self.shutdown_timeout = 10.0  # 关闭超时时间（秒）
        
        # 注册信号处理器
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except (AttributeError, ValueError):
            # Windows上可能不支持某些信号
            pass
    
    def _signal_handler(self, signum, frame):
        """信号处理函数"""
        self.logger.info(f"收到信号 {signum}，开始优雅关闭...")
        self.shutdown_gracefully()
    
    def register_cleanup_callback(self, callback: Callable[[], None], name: str = ""):
        """注册清理回调函数
        
        Args:
            callback: 清理函数
            name: 回调函数名称（用于日志）
        """
        self.cleanup_callbacks.append((callback, name))
        self.logger.debug(f"注册清理回调: {name or 'unnamed'}")
    
    def cleanup_and_exit(self, app=None, exit_code: int = 0, force: bool = False):
        """统一的应用退出处理
        
        Args:
            app: Qt应用实例
            exit_code: 退出码
            force: 是否强制退出（跳过清理）
        """
        if self.shutdown_in_progress and not force:
            self.logger.warning("关闭已在进行中，忽略重复请求")
            return
        
        self.shutdown_in_progress = True
        
        try:
            if not force:
                self.logger.info("开始应用清理...")
                
                # 执行清理回调
                self._execute_cleanup_callbacks()
                
                # 等待一小段时间确保清理完成
                time.sleep(0.1)
            
            # 退出Qt应用
            if app:
                self.logger.info("退出Qt应用...")
                try:
                    app.quit()
                    # 给Qt一些时间来处理退出
                    time.sleep(0.1)
                except Exception as e:
                    self.logger.error(f"Qt应用退出失败: {e}")
            
            self.logger.info(f"应用退出，退出码: {exit_code}")
            
        except Exception as e:
            self.logger.error(f"应用退出过程中发生错误: {e}")
            exit_code = 1
        
        finally:
            # 强制退出
            sys.exit(exit_code)
    
    def shutdown_gracefully(self, timeout: Optional[float] = None):
        """优雅关闭应用
        
        Args:
            timeout: 关闭超时时间，None使用默认值
        """
        if self.shutdown_in_progress:
            return
        
        timeout = timeout or self.shutdown_timeout
        self.logger.info(f"开始优雅关闭，超时时间: {timeout}秒")
        
        # 在单独线程中执行清理，避免阻塞
        cleanup_thread = threading.Thread(
            target=self._cleanup_with_timeout,
            args=(timeout,),
            daemon=True
        )
        cleanup_thread.start()
        cleanup_thread.join(timeout)
        
        if cleanup_thread.is_alive():
            self.logger.warning("清理超时，强制退出")
            self.cleanup_and_exit(force=True, exit_code=1)
        else:
            self.cleanup_and_exit(exit_code=0)
    
    def _cleanup_with_timeout(self, timeout: float):
        """带超时的清理执行"""
        start_time = time.time()
        
        for callback, name in self.cleanup_callbacks:
            if time.time() - start_time > timeout:
                self.logger.warning(f"清理超时，跳过剩余回调")
                break
            
            try:
                self.logger.debug(f"执行清理回调: {name or 'unnamed'}")
                callback()
            except Exception as e:
                self.logger.error(f"清理回调执行失败 [{name}]: {e}")
    
    def _execute_cleanup_callbacks(self):
        """执行所有清理回调"""
        for callback, name in self.cleanup_callbacks:
            try:
                self.logger.debug(f"执行清理回调: {name or 'unnamed'}")
                callback()
            except Exception as e:
                self.logger.error(f"清理回调执行失败 [{name}]: {e}")


# 全局生命周期管理器实例
_global_lifecycle_manager = None


def get_lifecycle_manager() -> AppLifecycleManager:
    """获取全局生命周期管理器实例"""
    global _global_lifecycle_manager
    if _global_lifecycle_manager is None:
        _global_lifecycle_manager = AppLifecycleManager()
    return _global_lifecycle_manager


def cleanup_and_exit(app=None, exit_code: int = 0, force: bool = False):
    """便捷函数：统一的应用退出处理
    
    这是最常用的退出函数，替代项目中重复的退出代码
    
    Args:
        app: Qt应用实例
        exit_code: 退出码
        force: 是否强制退出
    """
    manager = get_lifecycle_manager()
    manager.cleanup_and_exit(app, exit_code, force)


def register_cleanup_callback(callback: Callable[[], None], name: str = ""):
    """便捷函数：注册清理回调函数
    
    Args:
        callback: 清理函数
        name: 回调函数名称
    """
    manager = get_lifecycle_manager()
    manager.register_cleanup_callback(callback, name)


def shutdown_gracefully(timeout: Optional[float] = None):
    """便捷函数：优雅关闭应用
    
    Args:
        timeout: 关闭超时时间
    """
    manager = get_lifecycle_manager()
    manager.shutdown_gracefully(timeout)


# 常用的清理函数模板
def create_thread_cleanup(thread_obj, name: str = "") -> Callable[[], None]:
    """创建线程清理函数
    
    Args:
        thread_obj: 线程对象
        name: 线程名称
    
    Returns:
        清理函数
    """
    def cleanup():
        if hasattr(thread_obj, 'stop'):
            thread_obj.stop()
        if hasattr(thread_obj, 'join'):
            thread_obj.join(timeout=2.0)
    
    cleanup.__name__ = f"cleanup_thread_{name}"
    return cleanup


def create_process_cleanup(process_obj, name: str = "") -> Callable[[], None]:
    """创建进程清理函数
    
    Args:
        process_obj: 进程对象
        name: 进程名称
    
    Returns:
        清理函数
    """
    def cleanup():
        if hasattr(process_obj, 'terminate'):
            process_obj.terminate()
        if hasattr(process_obj, 'join'):
            process_obj.join(timeout=3.0)
        if hasattr(process_obj, 'kill'):
            process_obj.kill()
    
    cleanup.__name__ = f"cleanup_process_{name}"
    return cleanup


def create_resource_cleanup(resource_obj, cleanup_method: str = "close", 
                          name: str = "") -> Callable[[], None]:
    """创建资源清理函数
    
    Args:
        resource_obj: 资源对象
        cleanup_method: 清理方法名
        name: 资源名称
    
    Returns:
        清理函数
    """
    def cleanup():
        if hasattr(resource_obj, cleanup_method):
            method = getattr(resource_obj, cleanup_method)
            method()
    
    cleanup.__name__ = f"cleanup_resource_{name}"
    return cleanup

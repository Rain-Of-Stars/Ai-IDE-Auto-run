# -*- coding: utf-8 -*-
"""
异步网络任务模块

使用qasync将QApplication事件循环与asyncio结合：
- 高效的异步HTTP/WebSocket处理
- 与Qt信号槽系统无缝集成
- 严禁await长计算，CPU重活仍走multiprocessing
- 提供异步任务管理和错误处理
"""

import asyncio
import time
import traceback
from typing import Any, Callable, Optional, Dict, List, Union, Coroutine
from dataclasses import dataclass
import json

import aiohttp
import websockets
from PySide6 import QtCore
from PySide6.QtCore import QObject, Signal, QTimer

from auto_approve.logger_manager import get_logger

try:
    import qasync
    QASYNC_AVAILABLE = True
except ImportError:
    QASYNC_AVAILABLE = False
    qasync = None


@dataclass
class AsyncTaskResult:
    """异步任务结果"""
    task_id: str
    success: bool
    result: Any = None
    error_message: str = ""
    exception: Optional[Exception] = None
    execution_time: float = 0.0


class AsyncTaskSignals(QObject):
    """异步任务信号类"""
    # 任务完成信号：(task_id, result)
    task_completed = Signal(str, object)
    # 任务失败信号：(task_id, error_message, exception)
    task_failed = Signal(str, str, object)
    # 任务进度信号：(task_id, progress_percent, message)
    task_progress = Signal(str, int, str)


class AsyncTaskManager(QObject):
    """异步任务管理器
    
    管理asyncio任务，与Qt事件循环集成
    """
    
    def __init__(self):
        super().__init__()
        self._logger = get_logger()
        self.signals = AsyncTaskSignals()
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        if not QASYNC_AVAILABLE:
            self._logger.error("qasync不可用，异步功能将被禁用")
            raise ImportError("qasync库未安装，请运行: pip install qasync")
    
    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """设置事件循环"""
        self._loop = loop
        self._logger.info("异步任务管理器已设置事件循环")
    
    def submit_coroutine(self, coro: Coroutine, task_id: str = None) -> str:
        """提交协程任务
        
        Args:
            coro: 协程对象
            task_id: 任务ID，如果为None则自动生成
        
        Returns:
            str: 任务ID
        """
        if not self._loop:
            raise RuntimeError("事件循环未设置，请先调用set_event_loop")
        
        if task_id is None:
            task_id = f"async_task_{int(time.time() * 1000)}"
        
        # 包装协程以处理结果和异常
        wrapped_coro = self._wrap_coroutine(coro, task_id)
        
        # 创建任务
        task = self._loop.create_task(wrapped_coro)
        self._active_tasks[task_id] = task
        
        self._logger.debug(f"提交异步任务: {task_id}")
        return task_id
    
    async def _wrap_coroutine(self, coro: Coroutine, task_id: str):
        """包装协程以处理结果和异常"""
        start_time = time.time()
        
        try:
            result = await coro
            execution_time = time.time() - start_time
            
            # 发送成功信号
            self.signals.task_completed.emit(task_id, result)
            self._logger.debug(f"异步任务 {task_id} 完成，耗时: {execution_time:.3f}s")
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"异步任务执行失败: {str(e)}"
            
            # 发送失败信号
            self.signals.task_failed.emit(task_id, error_msg, e)
            self._logger.error(f"异步任务 {task_id} 失败: {error_msg}")
            self._logger.debug(f"异常详情: {traceback.format_exc()}")
        
        finally:
            # 从活跃任务中移除
            if task_id in self._active_tasks:
                del self._active_tasks[task_id]
    
    def cancel_task(self, task_id: str) -> bool:
        """取消指定任务"""
        if task_id in self._active_tasks:
            task = self._active_tasks[task_id]
            task.cancel()
            del self._active_tasks[task_id]
            self._logger.info(f"已取消异步任务: {task_id}")
            return True
        return False
    
    def cancel_all_tasks(self):
        """取消所有任务"""
        for task_id in list(self._active_tasks.keys()):
            self.cancel_task(task_id)
        self._logger.info("已取消所有异步任务")
    
    def get_active_task_count(self) -> int:
        """获取活跃任务数量"""
        return len(self._active_tasks)


# ==================== 异步任务函数 ====================

async def async_http_request(url: str, method: str = 'GET', 
                           headers: Dict = None, data: Any = None,
                           timeout: int = 30) -> Dict[str, Any]:
    """异步HTTP请求"""
    start_time = time.time()
    
    timeout_obj = aiohttp.ClientTimeout(total=timeout)
    
    async with aiohttp.ClientSession(timeout=timeout_obj) as session:
        async with session.request(method, url, headers=headers, data=data) as response:
            # 尝试解析JSON，失败则返回文本
            try:
                content = await response.json()
                content_type = 'json'
            except:
                content = await response.text()
                content_type = 'text'
            
            execution_time = time.time() - start_time
            
            return {
                'url': url,
                'method': method,
                'status_code': response.status,
                'headers': dict(response.headers),
                'content': content,
                'content_type': content_type,
                'execution_time': execution_time
            }


async def async_websocket_client(url: str, messages: List[str] = None,
                               timeout: int = 30) -> Dict[str, Any]:
    """异步WebSocket客户端"""
    start_time = time.time()
    received_messages = []
    
    try:
        async with websockets.connect(url, timeout=timeout) as websocket:
            # 发送消息
            if messages:
                for msg in messages:
                    await websocket.send(msg)
                    # 接收响应
                    response = await websocket.recv()
                    received_messages.append(response)
            
            execution_time = time.time() - start_time
            
            return {
                'url': url,
                'connected': True,
                'sent_messages': messages or [],
                'received_messages': received_messages,
                'execution_time': execution_time
            }
    
    except Exception as e:
        execution_time = time.time() - start_time
        return {
            'url': url,
            'connected': False,
            'error': str(e),
            'execution_time': execution_time
        }


async def async_batch_http_requests(urls: List[str], method: str = 'GET',
                                  max_concurrent: int = 10) -> List[Dict[str, Any]]:
    """批量异步HTTP请求"""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_one(url: str) -> Dict[str, Any]:
        async with semaphore:
            try:
                return await async_http_request(url, method)
            except Exception as e:
                return {
                    'url': url,
                    'error': str(e),
                    'success': False
                }
    
    # 并发执行所有请求
    tasks = [fetch_one(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 处理异常结果
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({
                'url': urls[i],
                'error': str(result),
                'success': False
            })
        else:
            processed_results.append(result)
    
    return processed_results


async def async_file_download(url: str, file_path: str, 
                            chunk_size: int = 8192) -> Dict[str, Any]:
    """异步文件下载"""
    start_time = time.time()
    downloaded_bytes = 0
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(file_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(chunk_size):
                    f.write(chunk)
                    downloaded_bytes += len(chunk)
            
            execution_time = time.time() - start_time
            
            return {
                'url': url,
                'file_path': file_path,
                'downloaded_bytes': downloaded_bytes,
                'total_size': total_size,
                'execution_time': execution_time,
                'success': True
            }


async def async_api_monitoring(api_urls: List[str], check_interval: int = 60,
                             max_checks: int = 10) -> Dict[str, Any]:
    """异步API监控"""
    results = {}
    
    for check_num in range(max_checks):
        check_start = time.time()
        
        # 并发检查所有API
        check_results = await async_batch_http_requests(api_urls)
        
        # 记录结果
        for result in check_results:
            url = result['url']
            if url not in results:
                results[url] = []
            
            results[url].append({
                'check_number': check_num + 1,
                'timestamp': check_start,
                'status_code': result.get('status_code'),
                'response_time': result.get('execution_time'),
                'success': 'error' not in result
            })
        
        # 等待下次检查
        if check_num < max_checks - 1:
            await asyncio.sleep(check_interval)
    
    return results


# 全局异步任务管理器实例
_global_async_manager: Optional[AsyncTaskManager] = None


def get_global_async_manager() -> AsyncTaskManager:
    """获取全局异步任务管理器实例"""
    global _global_async_manager
    if _global_async_manager is None:
        _global_async_manager = AsyncTaskManager()
    return _global_async_manager


def setup_qasync_event_loop(app) -> asyncio.AbstractEventLoop:
    """设置qasync事件循环"""
    if not QASYNC_AVAILABLE:
        raise ImportError("qasync库未安装")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    # 设置到异步任务管理器
    manager = get_global_async_manager()
    manager.set_event_loop(loop)

    return loop


# ==================== 便捷函数 ====================

def submit_async_http(url: str, method: str = 'GET', headers: Dict = None,
                     data: Any = None, timeout: int = 30,
                     on_success: Callable[[str, Any], None] = None,
                     on_error: Callable[[str, str, Exception], None] = None,
                     task_id: str = None) -> str:
    """便捷函数：提交异步HTTP请求"""
    manager = get_global_async_manager()

    # 连接信号
    if on_success:
        manager.signals.task_completed.connect(on_success)
    if on_error:
        manager.signals.task_failed.connect(on_error)

    coro = async_http_request(url, method, headers, data, timeout)
    return manager.submit_coroutine(coro, task_id)


def submit_async_websocket(url: str, messages: List[str] = None, timeout: int = 30,
                          on_success: Callable[[str, Any], None] = None,
                          on_error: Callable[[str, str, Exception], None] = None,
                          task_id: str = None) -> str:
    """便捷函数：提交异步WebSocket任务"""
    manager = get_global_async_manager()

    # 连接信号
    if on_success:
        manager.signals.task_completed.connect(on_success)
    if on_error:
        manager.signals.task_failed.connect(on_error)

    coro = async_websocket_client(url, messages, timeout)
    return manager.submit_coroutine(coro, task_id)


def submit_async_batch_requests(urls: List[str], method: str = 'GET',
                               max_concurrent: int = 10,
                               on_success: Callable[[str, Any], None] = None,
                               on_error: Callable[[str, str, Exception], None] = None,
                               task_id: str = None) -> str:
    """便捷函数：提交批量异步HTTP请求"""
    manager = get_global_async_manager()

    # 连接信号
    if on_success:
        manager.signals.task_completed.connect(on_success)
    if on_error:
        manager.signals.task_failed.connect(on_error)

    coro = async_batch_http_requests(urls, method, max_concurrent)
    return manager.submit_coroutine(coro, task_id)


def submit_async_download(url: str, file_path: str, chunk_size: int = 8192,
                         on_success: Callable[[str, Any], None] = None,
                         on_error: Callable[[str, str, Exception], None] = None,
                         task_id: str = None) -> str:
    """便捷函数：提交异步文件下载"""
    manager = get_global_async_manager()

    # 连接信号
    if on_success:
        manager.signals.task_completed.connect(on_success)
    if on_error:
        manager.signals.task_failed.connect(on_error)

    coro = async_file_download(url, file_path, chunk_size)
    return manager.submit_coroutine(coro, task_id)


def submit_async_monitoring(api_urls: List[str], check_interval: int = 60,
                           max_checks: int = 10,
                           on_success: Callable[[str, Any], None] = None,
                           on_error: Callable[[str, str, Exception], None] = None,
                           task_id: str = None) -> str:
    """便捷函数：提交异步API监控"""
    manager = get_global_async_manager()

    # 连接信号
    if on_success:
        manager.signals.task_completed.connect(on_success)
    if on_error:
        manager.signals.task_failed.connect(on_error)

    coro = async_api_monitoring(api_urls, check_interval, max_checks)
    return manager.submit_coroutine(coro, task_id)


def cancel_async_task(task_id: str) -> bool:
    """取消异步任务"""
    manager = get_global_async_manager()
    return manager.cancel_task(task_id)


def cancel_all_async_tasks():
    """取消所有异步任务"""
    manager = get_global_async_manager()
    manager.cancel_all_tasks()


def get_async_stats() -> Dict[str, Any]:
    """获取异步任务统计信息"""
    manager = get_global_async_manager()
    return {
        'active_tasks': manager.get_active_task_count(),
        'qasync_available': QASYNC_AVAILABLE,
        'event_loop_set': manager._loop is not None
    }

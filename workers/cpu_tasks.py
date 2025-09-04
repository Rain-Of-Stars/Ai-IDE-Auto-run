# -*- coding: utf-8 -*-
"""
CPU密集型任务模块

使用multiprocessing处理CPU密集型计算任务：
- 默认spawn启动方式，确保Windows兼容性
- 子进程只做纯计算，不触碰Qt对象
- 主进程使用Queue投递与QTimer 16ms轮询结果
- 提供submit_cpu(func, args, task_id)与cancel_all()接口
- 支持共享内存优化大数据传输
"""

import os
import sys
import time
import uuid
import pickle
import traceback
import multiprocessing as mp
from typing import Any, Callable, Optional, Dict, List, Tuple, Union
from dataclasses import dataclass
from queue import Empty
import numpy as np

from PySide6 import QtCore
from PySide6.QtCore import QObject, Signal, QTimer

from auto_approve.logger_manager import get_logger


# 确保Windows平台使用spawn方式启动进程
if sys.platform.startswith('win'):
    mp.set_start_method('spawn', force=True)


@dataclass
class CPUTaskResult:
    """CPU任务结果"""
    task_id: str
    success: bool
    result: Any = None
    error_message: str = ""
    exception: Optional[Exception] = None
    execution_time: float = 0.0
    worker_pid: int = 0


@dataclass
class CPUTaskRequest:
    """CPU任务请求"""
    task_id: str
    func_name: str
    func_module: str
    args: tuple
    kwargs: dict
    use_shared_memory: bool = False
    shared_memory_data: Optional[Dict] = None


class CPUTaskSignals(QObject):
    """CPU任务信号类"""
    # 任务完成信号：(task_id, result)
    task_completed = Signal(str, object)
    # 任务失败信号：(task_id, error_message, exception)
    task_failed = Signal(str, str, object)
    # 任务进度信号：(task_id, progress_percent, message)
    task_progress = Signal(str, int, str)


def _cpu_worker_process(task_queue: mp.Queue, result_queue: mp.Queue, worker_id: int):
    """CPU工作进程函数
    
    注意：此函数运行在独立进程中，不能访问Qt对象或主进程的全局变量
    """
    logger = get_logger()
    logger.info(f"CPU工作进程 {worker_id} (PID: {os.getpid()}) 已启动")
    
    while True:
        try:
            # 从任务队列获取任务，超时退出
            try:
                task_request: CPUTaskRequest = task_queue.get(timeout=30.0)
            except Empty:
                logger.debug(f"CPU工作进程 {worker_id} 超时退出")
                break
            
            # 检查是否为退出信号
            if task_request is None:
                logger.info(f"CPU工作进程 {worker_id} 收到退出信号")
                break
            
            start_time = time.time()
            
            try:
                # 动态导入函数
                module = __import__(task_request.func_module, fromlist=[task_request.func_name])
                func = getattr(module, task_request.func_name)
                
                # 执行任务
                result = func(*task_request.args, **task_request.kwargs)
                
                execution_time = time.time() - start_time
                
                # 创建成功结果
                task_result = CPUTaskResult(
                    task_id=task_request.task_id,
                    success=True,
                    result=result,
                    execution_time=execution_time,
                    worker_pid=os.getpid()
                )
                
                logger.debug(f"CPU任务 {task_request.task_id} 完成，耗时: {execution_time:.3f}s")
                
            except Exception as e:
                execution_time = time.time() - start_time
                error_msg = f"CPU任务执行失败: {str(e)}"
                
                # 创建失败结果
                task_result = CPUTaskResult(
                    task_id=task_request.task_id,
                    success=False,
                    error_message=error_msg,
                    exception=e,
                    execution_time=execution_time,
                    worker_pid=os.getpid()
                )
                
                logger.error(f"CPU任务 {task_request.task_id} 失败: {error_msg}")
                logger.debug(f"异常详情: {traceback.format_exc()}")
            
            # 将结果放入结果队列
            result_queue.put(task_result)
            
        except Exception as e:
            logger.error(f"CPU工作进程 {worker_id} 异常: {e}")
            logger.debug(f"异常详情: {traceback.format_exc()}")
            break
    
    logger.info(f"CPU工作进程 {worker_id} 已退出")


class CPUTaskManager(QObject):
    """CPU任务管理器
    
    管理multiprocessing进程池，处理CPU密集型任务
    """
    
    def __init__(self, max_workers: int = None):
        super().__init__()
        self._logger = get_logger()
        self.signals = CPUTaskSignals()
        
        # 进程池配置
        self._max_workers = max_workers or min(8, mp.cpu_count())
        self._processes: List[mp.Process] = []
        self._task_queue = mp.Queue()
        self._result_queue = mp.Queue()
        self._active_tasks: Dict[str, float] = {}  # task_id -> start_time
        
        # 结果轮询定时器
        self._result_timer = QTimer()
        self._result_timer.timeout.connect(self._poll_results)
        self._result_timer.setInterval(16)  # 16ms轮询，约60FPS
        
        # 启动标志
        self._started = False
        
        self._logger.info(f"CPU任务管理器初始化，最大工作进程数: {self._max_workers}")
    
    def start(self):
        """启动CPU任务管理器"""
        if self._started:
            return
        
        self._logger.info("启动CPU任务管理器...")
        
        # 启动工作进程
        for i in range(self._max_workers):
            process = mp.Process(
                target=_cpu_worker_process,
                args=(self._task_queue, self._result_queue, i),
                daemon=True
            )
            process.start()
            self._processes.append(process)
            self._logger.debug(f"启动CPU工作进程 {i} (PID: {process.pid})")
        
        # 启动结果轮询
        self._result_timer.start()
        self._started = True
        
        self._logger.info(f"CPU任务管理器已启动，{len(self._processes)} 个工作进程")
    
    def stop(self):
        """停止CPU任务管理器"""
        if not self._started:
            return
        
        self._logger.info("停止CPU任务管理器...")
        
        # 停止结果轮询
        self._result_timer.stop()
        
        # 发送退出信号给所有工作进程
        for _ in self._processes:
            self._task_queue.put(None)
        
        # 等待进程退出
        for process in self._processes:
            process.join(timeout=5.0)
            if process.is_alive():
                self._logger.warning(f"强制终止进程 {process.pid}")
                process.terminate()
                process.join(timeout=2.0)
        
        self._processes.clear()
        self._active_tasks.clear()
        self._started = False
        
        self._logger.info("CPU任务管理器已停止")
    
    def submit_task(self, func: Callable, args: tuple = (), kwargs: dict = None, 
                   task_id: str = None) -> str:
        """提交CPU任务
        
        Args:
            func: 要执行的函数
            args: 函数参数
            kwargs: 函数关键字参数
            task_id: 任务ID，如果为None则自动生成
        
        Returns:
            str: 任务ID
        """
        if not self._started:
            self.start()
        
        if task_id is None:
            task_id = f"cpu_task_{uuid.uuid4().hex[:8]}"
        
        if kwargs is None:
            kwargs = {}
        
        # 创建任务请求
        task_request = CPUTaskRequest(
            task_id=task_id,
            func_name=func.__name__,
            func_module=func.__module__,
            args=args,
            kwargs=kwargs
        )
        
        # 记录任务开始时间
        self._active_tasks[task_id] = time.time()
        
        # 提交任务到队列
        self._task_queue.put(task_request)
        
        self._logger.debug(f"提交CPU任务: {task_id}, 当前活跃任务: {len(self._active_tasks)}")
        
        return task_id
    
    def cancel_all(self):
        """取消所有待处理任务"""
        # 清空任务队列（注意：已在执行的任务无法取消）
        while not self._task_queue.empty():
            try:
                self._task_queue.get_nowait()
            except Empty:
                break
        
        self._logger.info("已清空CPU任务队列")
    
    def get_active_task_count(self) -> int:
        """获取活跃任务数量"""
        return len(self._active_tasks)
    
    def get_queue_size(self) -> int:
        """获取队列大小"""
        return self._task_queue.qsize()
    
    def _poll_results(self):
        """轮询任务结果"""
        processed_count = 0
        max_poll_per_cycle = 10  # 每次轮询最多处理10个结果，避免阻塞UI
        
        while processed_count < max_poll_per_cycle:
            try:
                result: CPUTaskResult = self._result_queue.get_nowait()
                processed_count += 1
                
                # 从活跃任务中移除
                if result.task_id in self._active_tasks:
                    del self._active_tasks[result.task_id]
                
                # 发送信号
                if result.success:
                    self.signals.task_completed.emit(result.task_id, result.result)
                else:
                    self.signals.task_failed.emit(result.task_id, result.error_message, result.exception)
                
                self._logger.debug(f"处理CPU任务结果: {result.task_id}, 成功: {result.success}")
                
            except Empty:
                break
            except Exception as e:
                self._logger.error(f"处理CPU任务结果异常: {e}")
                break


# 全局CPU任务管理器实例
_global_cpu_manager: Optional[CPUTaskManager] = None


def get_global_cpu_manager() -> CPUTaskManager:
    """获取全局CPU任务管理器实例"""
    global _global_cpu_manager
    if _global_cpu_manager is None:
        _global_cpu_manager = CPUTaskManager()
    return _global_cpu_manager


def submit_cpu(func: Callable, args: tuple = (), kwargs: dict = None, 
               task_id: str = None,
               on_success: Callable[[str, Any], None] = None,
               on_error: Callable[[str, str, Exception], None] = None) -> str:
    """便捷函数：提交CPU任务
    
    Args:
        func: 要执行的函数
        args: 函数参数
        kwargs: 函数关键字参数
        task_id: 任务ID
        on_success: 成功回调函数 (task_id, result)
        on_error: 错误回调函数 (task_id, error_message, exception)
    
    Returns:
        str: 任务ID
    """
    manager = get_global_cpu_manager()
    
    # 连接信号
    if on_success:
        manager.signals.task_completed.connect(on_success)
    if on_error:
        manager.signals.task_failed.connect(on_error)
    
    return manager.submit_task(func, args, kwargs, task_id)


def cancel_all():
    """取消所有CPU任务"""
    manager = get_global_cpu_manager()
    manager.cancel_all()


def get_cpu_stats() -> Dict[str, int]:
    """获取CPU任务统计信息"""
    manager = get_global_cpu_manager()
    return {
        'max_workers': manager._max_workers,
        'active_tasks': manager.get_active_task_count(),
        'queue_size': manager.get_queue_size(),
        'started': manager._started
    }


# ==================== CPU密集型任务示例函数 ====================
# 注意：这些函数将在独立进程中执行，不能访问Qt对象或主进程的全局变量

def cpu_intensive_calculation(n: int) -> Dict[str, Any]:
    """CPU密集型计算示例：计算斐波那契数列"""
    def fibonacci(num):
        if num <= 1:
            return num
        return fibonacci(num - 1) + fibonacci(num - 2)

    start_time = time.time()
    result = fibonacci(n)
    execution_time = time.time() - start_time

    return {
        'input': n,
        'result': result,
        'execution_time': execution_time,
        'worker_pid': os.getpid()
    }


def image_template_matching(image_data: np.ndarray, template_data: np.ndarray,
                          threshold: float = 0.8) -> Dict[str, Any]:
    """图像模板匹配（CPU密集型）"""
    import cv2

    start_time = time.time()

    # 执行模板匹配
    result = cv2.matchTemplate(image_data, template_data, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    # 检查是否匹配
    match_found = max_val >= threshold

    execution_time = time.time() - start_time

    return {
        'match_found': match_found,
        'max_confidence': float(max_val),
        'match_location': max_loc if match_found else None,
        'threshold': threshold,
        'execution_time': execution_time,
        'worker_pid': os.getpid()
    }


def batch_image_processing(images: List[np.ndarray], operation: str = 'blur') -> List[np.ndarray]:
    """批量图像处理（CPU密集型）"""
    import cv2

    processed_images = []

    for img in images:
        if operation == 'blur':
            processed = cv2.GaussianBlur(img, (15, 15), 0)
        elif operation == 'edge':
            processed = cv2.Canny(img, 100, 200)
        elif operation == 'gray':
            processed = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            processed = img.copy()

        processed_images.append(processed)

    return processed_images


def mathematical_computation(matrix_size: int = 1000) -> Dict[str, Any]:
    """数学计算示例：矩阵运算"""
    start_time = time.time()

    # 创建随机矩阵
    matrix_a = np.random.rand(matrix_size, matrix_size)
    matrix_b = np.random.rand(matrix_size, matrix_size)

    # 矩阵乘法
    result_matrix = np.dot(matrix_a, matrix_b)

    # 计算特征值
    eigenvalues = np.linalg.eigvals(result_matrix)

    execution_time = time.time() - start_time

    return {
        'matrix_size': matrix_size,
        'result_shape': result_matrix.shape,
        'eigenvalue_count': len(eigenvalues),
        'max_eigenvalue': float(np.max(eigenvalues.real)),
        'execution_time': execution_time,
        'worker_pid': os.getpid()
    }

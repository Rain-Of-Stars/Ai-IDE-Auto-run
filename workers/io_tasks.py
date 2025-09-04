# -*- coding: utf-8 -*-
"""
IO密集型任务模块

提供基于QThreadPool的IO任务处理框架：
- QRunnable任务基类，包含WorkerSignals(ok, err)
- 示例任务：HTTP拉取、磁盘读取等
- 异常统一回传err信号
- 全局QThreadPool复用，提供submit_io工具函数
"""

import os
import json
import time
import traceback
from typing import Any, Callable, Optional, Dict, List
from pathlib import Path

import requests
import cv2
import numpy as np
from PySide6 import QtCore
from PySide6.QtCore import QRunnable, QObject, Signal, QThreadPool, QTimer

from auto_approve.logger_manager import get_logger


class WorkerSignals(QObject):
    """工作线程信号类"""
    # 成功信号：(task_id, result)
    ok = Signal(str, object)
    # 错误信号：(task_id, error_message, exception)
    err = Signal(str, str, object)
    # 进度信号：(task_id, progress_percent, message)
    progress = Signal(str, int, str)


class IOTaskBase(QRunnable):
    """IO任务基类
    
    所有IO密集型任务的基类，提供统一的信号处理和异常捕获
    """
    
    def __init__(self, task_id: str = None):
        super().__init__()
        self.task_id = task_id or f"io_task_{int(time.time() * 1000)}"
        self.signals = WorkerSignals()
        self._logger = get_logger()
        
    def run(self):
        """QRunnable接口实现，子类应重写execute方法"""
        try:
            result = self.execute()
            self.signals.ok.emit(self.task_id, result)
        except Exception as e:
            error_msg = f"IO任务执行失败: {str(e)}"
            self._logger.error(f"[{self.task_id}] {error_msg}")
            self._logger.debug(f"[{self.task_id}] 异常详情: {traceback.format_exc()}")
            self.signals.err.emit(self.task_id, error_msg, e)
    
    def execute(self) -> Any:
        """子类需要实现的具体执行逻辑"""
        raise NotImplementedError("子类必须实现execute方法")
    
    def emit_progress(self, progress: int, message: str = ""):
        """发射进度信号"""
        self.signals.progress.emit(self.task_id, progress, message)


class FileReadTask(IOTaskBase):
    """文件读取任务"""
    
    def __init__(self, file_path: str, encoding: str = 'utf-8', task_id: str = None):
        super().__init__(task_id)
        self.file_path = file_path
        self.encoding = encoding
    
    def execute(self) -> Dict[str, Any]:
        """执行文件读取"""
        self.emit_progress(10, f"开始读取文件: {self.file_path}")
        
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"文件不存在: {self.file_path}")
        
        self.emit_progress(30, "检查文件权限")
        
        # 根据文件扩展名选择读取方式
        file_ext = Path(self.file_path).suffix.lower()
        
        if file_ext == '.json':
            self.emit_progress(50, "读取JSON文件")
            with open(self.file_path, 'r', encoding=self.encoding) as f:
                content = json.load(f)
        elif file_ext in ['.png', '.jpg', '.jpeg', '.bmp']:
            self.emit_progress(50, "读取图像文件")
            # 使用cv2.imdecode处理中文路径
            img_data = np.fromfile(self.file_path, dtype=np.uint8)
            content = cv2.imdecode(img_data, cv2.IMREAD_UNCHANGED)
            if content is None:
                raise ValueError(f"无法解码图像文件: {self.file_path}")
        else:
            self.emit_progress(50, "读取文本文件")
            with open(self.file_path, 'r', encoding=self.encoding) as f:
                content = f.read()
        
        self.emit_progress(100, "文件读取完成")
        
        return {
            'file_path': self.file_path,
            'content': content,
            'file_size': os.path.getsize(self.file_path),
            'file_type': file_ext
        }


class FileWriteTask(IOTaskBase):
    """文件写入任务"""
    
    def __init__(self, file_path: str, content: Any, encoding: str = 'utf-8', task_id: str = None):
        super().__init__(task_id)
        self.file_path = file_path
        self.content = content
        self.encoding = encoding
    
    def execute(self) -> Dict[str, Any]:
        """执行文件写入"""
        self.emit_progress(10, f"开始写入文件: {self.file_path}")
        
        # 确保目录存在
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        
        self.emit_progress(30, "创建目录")
        
        file_ext = Path(self.file_path).suffix.lower()
        
        if file_ext == '.json':
            self.emit_progress(50, "写入JSON文件")
            with open(self.file_path, 'w', encoding=self.encoding) as f:
                json.dump(self.content, f, ensure_ascii=False, indent=2)
        elif file_ext in ['.png', '.jpg', '.jpeg', '.bmp']:
            self.emit_progress(50, "写入图像文件")
            if isinstance(self.content, np.ndarray):
                # 使用cv2.imencode处理中文路径
                success, encoded_img = cv2.imencode(file_ext, self.content)
                if success:
                    encoded_img.tofile(self.file_path)
                else:
                    raise ValueError(f"无法编码图像: {self.file_path}")
            else:
                raise TypeError("图像文件需要numpy.ndarray类型的内容")
        else:
            self.emit_progress(50, "写入文本文件")
            with open(self.file_path, 'w', encoding=self.encoding) as f:
                f.write(str(self.content))
        
        self.emit_progress(100, "文件写入完成")
        
        return {
            'file_path': self.file_path,
            'file_size': os.path.getsize(self.file_path),
            'success': True
        }


class HTTPRequestTask(IOTaskBase):
    """HTTP请求任务"""
    
    def __init__(self, url: str, method: str = 'GET', headers: Dict = None, 
                 data: Any = None, timeout: int = 30, task_id: str = None):
        super().__init__(task_id)
        self.url = url
        self.method = method.upper()
        self.headers = headers or {}
        self.data = data
        self.timeout = timeout
    
    def execute(self) -> Dict[str, Any]:
        """执行HTTP请求"""
        self.emit_progress(10, f"准备{self.method}请求: {self.url}")
        
        # 设置默认User-Agent
        if 'User-Agent' not in self.headers:
            self.headers['User-Agent'] = 'AI-IDE-Auto-Run/1.0'
        
        self.emit_progress(30, "发送HTTP请求")
        
        response = requests.request(
            method=self.method,
            url=self.url,
            headers=self.headers,
            data=self.data,
            timeout=self.timeout
        )
        
        self.emit_progress(70, f"收到响应: {response.status_code}")
        
        # 检查响应状态
        response.raise_for_status()
        
        self.emit_progress(90, "解析响应内容")
        
        # 尝试解析JSON，失败则返回文本
        try:
            content = response.json()
            content_type = 'json'
        except:
            content = response.text
            content_type = 'text'
        
        self.emit_progress(100, "HTTP请求完成")
        
        return {
            'url': self.url,
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'content': content,
            'content_type': content_type,
            'encoding': response.encoding
        }


class BatchFileLoadTask(IOTaskBase):
    """批量文件加载任务"""
    
    def __init__(self, file_paths: List[str], task_id: str = None):
        super().__init__(task_id)
        self.file_paths = file_paths
    
    def execute(self) -> Dict[str, Any]:
        """执行批量文件加载"""
        results = {}
        failed_files = []
        total_files = len(self.file_paths)
        
        for i, file_path in enumerate(self.file_paths):
            progress = int((i / total_files) * 100)
            self.emit_progress(progress, f"加载文件 {i+1}/{total_files}: {os.path.basename(file_path)}")
            
            try:
                # 创建子任务进行文件读取
                read_task = FileReadTask(file_path)
                result = read_task.execute()
                results[file_path] = result
            except Exception as e:
                self._logger.warning(f"加载文件失败: {file_path}, 错误: {e}")
                failed_files.append({'file_path': file_path, 'error': str(e)})
        
        self.emit_progress(100, f"批量加载完成，成功: {len(results)}, 失败: {len(failed_files)}")
        
        return {
            'successful_files': results,
            'failed_files': failed_files,
            'total_count': total_files,
            'success_count': len(results),
            'failed_count': len(failed_files)
        }


# 全局线程池实例
_global_thread_pool: Optional[QThreadPool] = None


def get_global_thread_pool() -> QThreadPool:
    """获取全局线程池实例"""
    global _global_thread_pool
    if _global_thread_pool is None:
        _global_thread_pool = QThreadPool.globalInstance()
        # 设置合理的线程数量，避免过多线程竞争
        max_threads = min(8, (_global_thread_pool.maxThreadCount() // 2) or 4)
        _global_thread_pool.setMaxThreadCount(max_threads)
        get_logger().info(f"初始化全局IO线程池，最大线程数: {max_threads}")
    return _global_thread_pool


def submit_io(task: IOTaskBase, 
              on_success: Callable[[str, Any], None] = None,
              on_error: Callable[[str, str, Exception], None] = None,
              on_progress: Callable[[str, int, str], None] = None) -> str:
    """提交IO任务到线程池
    
    Args:
        task: IO任务实例
        on_success: 成功回调函数 (task_id, result)
        on_error: 错误回调函数 (task_id, error_message, exception)
        on_progress: 进度回调函数 (task_id, progress_percent, message)
    
    Returns:
        str: 任务ID
    """
    thread_pool = get_global_thread_pool()
    
    # 连接信号
    if on_success:
        task.signals.ok.connect(on_success)
    if on_error:
        task.signals.err.connect(on_error)
    if on_progress:
        task.signals.progress.connect(on_progress)
    
    # 提交任务
    thread_pool.start(task)
    
    get_logger().debug(f"提交IO任务: {task.task_id}, 当前活跃线程: {thread_pool.activeThreadCount()}")
    
    return task.task_id


def submit_file_read(file_path: str,
                     on_success: Callable[[str, Any], None] = None,
                     on_error: Callable[[str, str, Exception], None] = None,
                     encoding: str = 'utf-8',
                     task_id: str = None) -> str:
    """便捷函数：提交文件读取任务"""
    task = FileReadTask(file_path, encoding, task_id)
    return submit_io(task, on_success, on_error)


def submit_file_write(file_path: str, content: Any,
                      on_success: Callable[[str, Any], None] = None,
                      on_error: Callable[[str, str, Exception], None] = None,
                      encoding: str = 'utf-8',
                      task_id: str = None) -> str:
    """便捷函数：提交文件写入任务"""
    task = FileWriteTask(file_path, content, encoding, task_id)
    return submit_io(task, on_success, on_error)


def submit_http_request(url: str, method: str = 'GET',
                        on_success: Callable[[str, Any], None] = None,
                        on_error: Callable[[str, str, Exception], None] = None,
                        headers: Dict = None, data: Any = None,
                        timeout: int = 30, task_id: str = None) -> str:
    """便捷函数：提交HTTP请求任务"""
    task = HTTPRequestTask(url, method, headers, data, timeout, task_id)
    return submit_io(task, on_success, on_error)


def get_thread_pool_stats() -> Dict[str, int]:
    """获取线程池统计信息"""
    pool = get_global_thread_pool()
    return {
        'max_thread_count': pool.maxThreadCount(),
        'active_thread_count': pool.activeThreadCount(),
        'expiry_timeout': pool.expiryTimeout()
    }


# ==================== 扩展的IO任务类型 ====================

class DatabaseTask(IOTaskBase):
    """数据库操作任务（示例）"""

    def __init__(self, query: str, params: tuple = (), task_id: str = None):
        super().__init__(task_id)
        self.query = query
        self.params = params

    def execute(self) -> Dict[str, Any]:
        """执行数据库查询（这里是模拟实现）"""
        self.emit_progress(20, "连接数据库")
        time.sleep(0.1)  # 模拟连接延迟

        self.emit_progress(50, "执行查询")
        time.sleep(0.2)  # 模拟查询延迟

        self.emit_progress(80, "处理结果")

        # 模拟查询结果
        result = {
            'query': self.query,
            'params': self.params,
            'rows_affected': 5,
            'execution_time': 0.3,
            'timestamp': time.time()
        }

        self.emit_progress(100, "查询完成")
        return result


class WebSocketTask(IOTaskBase):
    """WebSocket连接任务"""

    def __init__(self, url: str, message: str = None, timeout: int = 30, task_id: str = None):
        super().__init__(task_id)
        self.url = url
        self.message = message
        self.timeout = timeout

    def execute(self) -> Dict[str, Any]:
        """执行WebSocket连接（模拟实现）"""
        self.emit_progress(10, f"连接WebSocket: {self.url}")

        # 这里应该使用真实的WebSocket库，如websocket-client
        # 为了避免额外依赖，这里只是模拟
        time.sleep(0.5)  # 模拟连接时间

        self.emit_progress(50, "连接已建立")

        if self.message:
            self.emit_progress(70, "发送消息")
            time.sleep(0.2)  # 模拟发送时间

        self.emit_progress(90, "接收响应")
        time.sleep(0.1)  # 模拟接收时间

        result = {
            'url': self.url,
            'connected': True,
            'message_sent': self.message,
            'response': f"Echo: {self.message}" if self.message else None,
            'timestamp': time.time()
        }

        self.emit_progress(100, "WebSocket任务完成")
        return result


class ConfigurationTask(IOTaskBase):
    """配置文件操作任务"""

    def __init__(self, config_path: str, operation: str = 'read',
                 config_data: Dict = None, task_id: str = None):
        super().__init__(task_id)
        self.config_path = config_path
        self.operation = operation  # 'read', 'write', 'update'
        self.config_data = config_data or {}

    def execute(self) -> Dict[str, Any]:
        """执行配置文件操作"""
        config_path = Path(self.config_path)

        if self.operation == 'read':
            self.emit_progress(30, f"读取配置文件: {config_path.name}")

            if not config_path.exists():
                raise FileNotFoundError(f"配置文件不存在: {config_path}")

            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.suffix.lower() == '.json':
                    config_data = json.load(f)
                else:
                    config_data = f.read()

            self.emit_progress(100, "配置读取完成")
            return {
                'operation': 'read',
                'config_path': str(config_path),
                'config_data': config_data,
                'file_size': config_path.stat().st_size
            }

        elif self.operation == 'write':
            self.emit_progress(30, f"写入配置文件: {config_path.name}")

            # 确保目录存在
            config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(config_path, 'w', encoding='utf-8') as f:
                if config_path.suffix.lower() == '.json':
                    json.dump(self.config_data, f, indent=2, ensure_ascii=False)
                else:
                    f.write(str(self.config_data))

            self.emit_progress(100, "配置写入完成")
            return {
                'operation': 'write',
                'config_path': str(config_path),
                'bytes_written': config_path.stat().st_size
            }

        elif self.operation == 'update':
            self.emit_progress(20, f"更新配置文件: {config_path.name}")

            # 先读取现有配置
            existing_config = {}
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    if config_path.suffix.lower() == '.json':
                        existing_config = json.load(f)

            self.emit_progress(60, "合并配置数据")

            # 合并配置
            if isinstance(existing_config, dict) and isinstance(self.config_data, dict):
                existing_config.update(self.config_data)
                merged_config = existing_config
            else:
                merged_config = self.config_data

            # 写入更新后的配置
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                if config_path.suffix.lower() == '.json':
                    json.dump(merged_config, f, indent=2, ensure_ascii=False)
                else:
                    f.write(str(merged_config))

            self.emit_progress(100, "配置更新完成")
            return {
                'operation': 'update',
                'config_path': str(config_path),
                'merged_config': merged_config,
                'bytes_written': config_path.stat().st_size
            }

        else:
            raise ValueError(f"不支持的操作类型: {self.operation}")


class LogAnalysisTask(IOTaskBase):
    """日志分析任务"""

    def __init__(self, log_path: str, pattern: str = None,
                 max_lines: int = 10000, task_id: str = None):
        super().__init__(task_id)
        self.log_path = log_path
        self.pattern = pattern
        self.max_lines = max_lines

    def execute(self) -> Dict[str, Any]:
        """执行日志分析"""
        import re

        log_path = Path(self.log_path)
        if not log_path.exists():
            raise FileNotFoundError(f"日志文件不存在: {log_path}")

        self.emit_progress(10, f"开始分析日志: {log_path.name}")

        total_lines = 0
        matched_lines = []
        error_count = 0
        warning_count = 0

        pattern_regex = re.compile(self.pattern) if self.pattern else None

        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                if line_num > self.max_lines:
                    break

                total_lines += 1
                line = line.strip()

                # 统计错误和警告
                if 'ERROR' in line.upper() or 'FATAL' in line.upper():
                    error_count += 1
                elif 'WARNING' in line.upper() or 'WARN' in line.upper():
                    warning_count += 1

                # 模式匹配
                if pattern_regex and pattern_regex.search(line):
                    matched_lines.append({
                        'line_number': line_num,
                        'content': line
                    })

                # 更新进度
                if line_num % 1000 == 0:
                    progress = min(90, int((line_num / self.max_lines) * 90))
                    self.emit_progress(progress, f"已分析 {line_num} 行")

        self.emit_progress(100, "日志分析完成")

        return {
            'log_path': str(log_path),
            'total_lines': total_lines,
            'error_count': error_count,
            'warning_count': warning_count,
            'matched_lines': matched_lines[:100],  # 最多返回100个匹配行
            'pattern': self.pattern,
            'file_size': log_path.stat().st_size
        }


# ==================== 扩展的便捷函数 ====================

def submit_database_query(query: str, params: tuple = (),
                         on_success: Callable[[str, Any], None] = None,
                         on_error: Callable[[str, str, Exception], None] = None,
                         task_id: str = None) -> str:
    """便捷函数：提交数据库查询任务"""
    task = DatabaseTask(query, params, task_id)
    return submit_io(task, on_success, on_error)


def submit_websocket_task(url: str, message: str = None,
                         on_success: Callable[[str, Any], None] = None,
                         on_error: Callable[[str, str, Exception], None] = None,
                         timeout: int = 30, task_id: str = None) -> str:
    """便捷函数：提交WebSocket任务"""
    task = WebSocketTask(url, message, timeout, task_id)
    return submit_io(task, on_success, on_error)


def submit_config_operation(config_path: str, operation: str = 'read',
                           config_data: Dict = None,
                           on_success: Callable[[str, Any], None] = None,
                           on_error: Callable[[str, str, Exception], None] = None,
                           task_id: str = None) -> str:
    """便捷函数：提交配置文件操作任务"""
    task = ConfigurationTask(config_path, operation, config_data, task_id)
    return submit_io(task, on_success, on_error)


def submit_log_analysis(log_path: str, pattern: str = None, max_lines: int = 10000,
                       on_success: Callable[[str, Any], None] = None,
                       on_error: Callable[[str, str, Exception], None] = None,
                       task_id: str = None) -> str:
    """便捷函数：提交日志分析任务"""
    task = LogAnalysisTask(log_path, pattern, max_lines, task_id)
    return submit_io(task, on_success, on_error)


def optimize_thread_pool(cpu_intensive_ratio: float = 0.3):
    """优化线程池配置

    Args:
        cpu_intensive_ratio: CPU密集型任务比例，用于调整线程数
    """
    pool = get_global_thread_pool()

    # 获取系统信息
    import os
    cpu_count = os.cpu_count() or 4

    # 根据任务类型调整线程数
    # IO密集型任务可以使用更多线程
    if cpu_intensive_ratio < 0.2:
        # 主要是IO任务，可以使用更多线程
        optimal_threads = min(32, cpu_count * 4)
    elif cpu_intensive_ratio > 0.7:
        # 主要是CPU任务，使用较少线程
        optimal_threads = max(2, cpu_count)
    else:
        # 混合任务，使用中等数量线程
        optimal_threads = min(16, cpu_count * 2)

    pool.setMaxThreadCount(optimal_threads)
    get_logger().info(f"线程池已优化，最大线程数: {optimal_threads} (CPU核心数: {cpu_count})")


def cleanup_thread_pool():
    """清理线程池资源"""
    global _global_thread_pool
    if _global_thread_pool:
        _global_thread_pool.waitForDone(5000)  # 等待5秒
        active_count = _global_thread_pool.activeThreadCount()
        if active_count > 0:
            get_logger().warning(f"线程池清理时仍有 {active_count} 个活跃线程")
        _global_thread_pool = None
        get_logger().info("线程池已清理")


def get_detailed_thread_pool_stats() -> Dict[str, Any]:
    """获取详细的线程池统计信息"""
    pool = get_global_thread_pool()

    return {
        'max_thread_count': pool.maxThreadCount(),
        'active_thread_count': pool.activeThreadCount(),
        'expiry_timeout': pool.expiryTimeout(),
        'reserved_thread_count': getattr(pool, 'reservedThreadCount', lambda: 0)(),
        'stack_size': pool.stackSize(),
        'thread_priority': pool.threadPriority()
    }

# -*- coding: utf-8 -*-
"""
统一的测试工具模块

集中定义所有测试相关的工具类和函数，避免重复定义
"""

import sys
import time
import threading
from typing import Any, Dict, List, Optional, Callable
from unittest.mock import Mock, MagicMock
from pathlib import Path


class MockNumpy:
    """统一的NumPy模拟类
    
    整合了原有的多个MockNumpy定义，提供完整的NumPy模拟功能
    """
    
    def __init__(self):
        self.array_data = {}
        self.call_count = 0
        self.last_operation = None
    
    def array(self, data, dtype=None):
        """模拟numpy.array"""
        self.call_count += 1
        self.last_operation = 'array'
        
        if isinstance(data, list):
            # 简单的列表转换
            return MockArray(data, dtype=dtype)
        elif hasattr(data, 'shape'):
            # 已经是数组对象
            return data
        else:
            # 其他类型
            return MockArray([data], dtype=dtype)
    
    def zeros(self, shape, dtype=None):
        """模拟numpy.zeros"""
        self.call_count += 1
        self.last_operation = 'zeros'
        
        if isinstance(shape, int):
            data = [0] * shape
        elif isinstance(shape, (list, tuple)) and len(shape) == 2:
            data = [[0] * shape[1] for _ in range(shape[0])]
        else:
            data = [0]
        
        return MockArray(data, dtype=dtype)
    
    def ones(self, shape, dtype=None):
        """模拟numpy.ones"""
        self.call_count += 1
        self.last_operation = 'ones'
        
        if isinstance(shape, int):
            data = [1] * shape
        elif isinstance(shape, (list, tuple)) and len(shape) == 2:
            data = [[1] * shape[1] for _ in range(shape[0])]
        else:
            data = [1]
        
        return MockArray(data, dtype=dtype)
    
    def asarray(self, data, dtype=None):
        """模拟numpy.asarray"""
        self.call_count += 1
        self.last_operation = 'asarray'
        return self.array(data, dtype=dtype)
    
    def ascontiguousarray(self, data):
        """模拟numpy.ascontiguousarray"""
        self.call_count += 1
        self.last_operation = 'ascontiguousarray'
        
        if hasattr(data, 'flags'):
            # 模拟设置连续标志
            data.flags['C_CONTIGUOUS'] = True
        
        return data
    
    # 数据类型
    uint8 = 'uint8'
    float32 = 'float32'
    float64 = 'float64'
    int32 = 'int32'


class MockArray:
    """模拟的NumPy数组类"""
    
    def __init__(self, data, dtype=None):
        self.data = data
        self.dtype = dtype
        self.flags = {'C_CONTIGUOUS': True}
        
        # 计算shape
        if isinstance(data, list):
            if data and isinstance(data[0], list):
                self.shape = (len(data), len(data[0]))
            else:
                self.shape = (len(data),)
        else:
            self.shape = ()
    
    def __getitem__(self, key):
        return self.data[key]
    
    def __setitem__(self, key, value):
        self.data[key] = value
    
    def copy(self):
        """复制数组"""
        return MockArray(self.data.copy() if hasattr(self.data, 'copy') else self.data, self.dtype)


class MockOpenCV:
    """OpenCV模拟类"""
    
    def __init__(self):
        self.call_count = 0
        self.last_operation = None
    
    def imread(self, filename, flags=None):
        """模拟cv2.imread"""
        self.call_count += 1
        self.last_operation = 'imread'
        
        # 返回模拟的图像数组
        return MockArray([[100, 150, 200]] * 100, dtype='uint8')
    
    def imwrite(self, filename, img):
        """模拟cv2.imwrite"""
        self.call_count += 1
        self.last_operation = 'imwrite'
        return True
    
    def cvtColor(self, src, code):
        """模拟cv2.cvtColor"""
        self.call_count += 1
        self.last_operation = 'cvtColor'
        return src  # 简单返回原图
    
    def matchTemplate(self, image, template, method):
        """模拟cv2.matchTemplate"""
        self.call_count += 1
        self.last_operation = 'matchTemplate'
        
        # 返回模拟的匹配结果
        return MockArray([[0.8, 0.6], [0.7, 0.9]], dtype='float32')
    
    def minMaxLoc(self, src):
        """模拟cv2.minMaxLoc"""
        self.call_count += 1
        self.last_operation = 'minMaxLoc'
        
        # 返回 (minVal, maxVal, minLoc, maxLoc)
        return (0.1, 0.9, (0, 0), (1, 1))
    
    # 常量
    COLOR_BGR2RGB = 4
    COLOR_BGR2GRAY = 6
    TM_CCOEFF_NORMED = 3


class MockPySide6:
    """PySide6模拟类"""
    
    class QtCore:
        class QObject:
            def __init__(self):
                pass
        
        class Signal:
            def __init__(self, *args):
                self.connections = []
            
            def connect(self, slot):
                self.connections.append(slot)
            
            def emit(self, *args):
                for slot in self.connections:
                    try:
                        slot(*args)
                    except:
                        pass
        
        class QTimer:
            def __init__(self):
                self.timeout = MockPySide6.QtCore.Signal()
                self.interval = 1000
                self.single_shot = False
            
            def start(self, msec=None):
                if msec:
                    self.interval = msec
            
            def stop(self):
                pass
            
            def setSingleShot(self, single):
                self.single_shot = single
    
    class QtWidgets:
        class QApplication:
            def __init__(self, args):
                pass
            
            def exec(self):
                return 0


class TestTimer:
    """测试计时器"""
    
    def __init__(self, name: str = ""):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.duration = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        self.duration = self.end_time - self.start_time
        
        if self.name:
            print(f"[{self.name}] 耗时: {self.duration:.3f}秒")
    
    def elapsed(self) -> float:
        """获取已经过的时间"""
        if self.start_time is None:
            return 0.0
        
        current = time.perf_counter()
        return current - self.start_time


class MockLogger:
    """模拟日志器"""
    
    def __init__(self):
        self.logs = []
    
    def info(self, msg, *args):
        self.logs.append(('INFO', msg % args if args else msg))
    
    def warning(self, msg, *args):
        self.logs.append(('WARNING', msg % args if args else msg))
    
    def error(self, msg, *args):
        self.logs.append(('ERROR', msg % args if args else msg))
    
    def debug(self, msg, *args):
        self.logs.append(('DEBUG', msg % args if args else msg))
    
    def get_logs(self, level: str = None) -> List[str]:
        """获取日志记录"""
        if level:
            return [msg for lvl, msg in self.logs if lvl == level.upper()]
        return [msg for lvl, msg in self.logs]
    
    def clear(self):
        """清空日志"""
        self.logs.clear()


def setup_test_environment():
    """设置测试环境"""
    # 添加项目根目录到路径
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def create_mock_config(**kwargs) -> Dict[str, Any]:
    """创建模拟配置"""
    default_config = {
        'template_path': 'test_template.png',
        'template_paths': [],
        'monitor_index': 1,
        'interval_ms': 1000,
        'threshold': 0.8,
        'cooldown_s': 2.0,
        'enable_logging': False,
        'enable_notifications': True,
        'grayscale': True,
        'multi_scale': False,
        'debug_mode': False
    }
    
    default_config.update(kwargs)
    return default_config


def wait_for_condition(condition: Callable[[], bool], timeout: float = 5.0, 
                      interval: float = 0.1) -> bool:
    """等待条件满足"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if condition():
            return True
        time.sleep(interval)
    
    return False


def run_in_thread(func: Callable, *args, **kwargs) -> threading.Thread:
    """在线程中运行函数"""
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()
    return thread


# 全局模拟对象实例
mock_numpy = MockNumpy()
mock_opencv = MockOpenCV()
mock_pyside6 = MockPySide6()
mock_logger = MockLogger()


# 便捷函数
def get_mock_numpy() -> MockNumpy:
    """获取NumPy模拟对象"""
    return mock_numpy


def get_mock_opencv() -> MockOpenCV:
    """获取OpenCV模拟对象"""
    return mock_opencv


def get_mock_logger() -> MockLogger:
    """获取日志模拟对象"""
    return mock_logger


def reset_mocks():
    """重置所有模拟对象"""
    global mock_numpy, mock_opencv, mock_logger
    mock_numpy = MockNumpy()
    mock_opencv = MockOpenCV()
    mock_logger = MockLogger()

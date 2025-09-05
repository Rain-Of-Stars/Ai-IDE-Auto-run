# -*- coding: utf-8 -*-
"""
多线程架构测试

验证新的多线程架构的正确性和性能：
- IO任务处理测试
- CPU任务处理测试
- 异步任务处理测试
- 性能监控测试
- 线程安全测试
"""

import sys
import os
import time
import unittest
import threading
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtWidgets, QtCore, QtTest
from PySide6.QtCore import QTimer, QEventLoop

# 导入多线程模块
from workers.io_tasks import (submit_io, FileReadTask, HTTPRequestTask, 
                             get_global_thread_pool, get_thread_pool_stats)
from workers.cpu_tasks import (submit_cpu, get_global_cpu_manager, get_cpu_stats,
                              cpu_intensive_calculation, mathematical_computation)
from workers.async_tasks import (setup_qasync_event_loop, submit_async_http,
                                get_global_async_manager, get_async_stats, QASYNC_AVAILABLE)

# 导入性能分析器
from utils.performance_profiler import get_global_profiler, measure_performance, record_milestone

from auto_approve.logger_manager import get_logger


class TestIOTasks(unittest.TestCase):
    """IO任务测试"""
    
    def setUp(self):
        """测试设置"""
        self.app = QtWidgets.QApplication.instance()
        if self.app is None:
            self.app = QtWidgets.QApplication([])
        
        self.logger = get_logger()
        self.results = []
        self.errors = []
    
    def tearDown(self):
        """测试清理"""
        # 等待所有任务完成
        pool = get_global_thread_pool()
        pool.waitForDone(5000)
    
    def test_file_read_task(self):
        """测试文件读取任务"""
        # 创建临时文件
        test_file = "test_file.txt"
        test_content = "Hello, World!\n测试内容"
        
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        try:
            # 提交文件读取任务
            task = FileReadTask(test_file)
            
            def on_success(task_id, result):
                self.results.append(result)
            
            def on_error(task_id, error, exc):
                self.errors.append(error)
            
            submit_io(task, on_success, on_error)
            
            # 等待任务完成
            start_time = time.time()
            while not self.results and not self.errors and time.time() - start_time < 5:
                self.app.processEvents()
                time.sleep(0.01)
            
            # 验证结果
            self.assertEqual(len(self.errors), 0, f"文件读取出错: {self.errors}")
            self.assertEqual(len(self.results), 1, "应该有一个结果")
            self.assertEqual(self.results[0]['content'], test_content)
            
        finally:
            # 清理临时文件
            if os.path.exists(test_file):
                os.remove(test_file)
    
    def test_http_request_task(self):
        """测试HTTP请求任务"""
        # 使用httpbin.org进行测试
        url = "https://httpbin.org/get"
        
        task = HTTPRequestTask(url)
        
        def on_success(task_id, result):
            self.results.append(result)
        
        def on_error(task_id, error, exc):
            self.errors.append(error)
        
        submit_io(task, on_success, on_error)
        
        # 等待任务完成
        start_time = time.time()
        while not self.results and not self.errors and time.time() - start_time < 10:
            self.app.processEvents()
            time.sleep(0.01)
        
        # 验证结果
        if self.errors:
            self.skipTest(f"网络请求失败，可能是网络问题: {self.errors[0]}")
        
        self.assertEqual(len(self.results), 1, "应该有一个结果")
        self.assertEqual(self.results[0]['status_code'], 200)
        self.assertIn('url', self.results[0])
    
    def test_concurrent_io_tasks(self):
        """测试并发IO任务"""
        task_count = 5
        
        # 创建多个临时文件
        test_files = []
        for i in range(task_count):
            file_name = f"test_file_{i}.txt"
            content = f"Test content {i}"
            
            with open(file_name, 'w', encoding='utf-8') as f:
                f.write(content)
            
            test_files.append((file_name, content))
        
        try:
            # 提交多个文件读取任务
            for file_name, expected_content in test_files:
                task = FileReadTask(file_name)
                
                def on_success(task_id, result, expected=expected_content):
                    result['expected'] = expected
                    self.results.append(result)
                
                def on_error(task_id, error, exc):
                    self.errors.append(error)
                
                submit_io(task, on_success, on_error)
            
            # 等待所有任务完成
            start_time = time.time()
            while len(self.results) + len(self.errors) < task_count and time.time() - start_time < 10:
                self.app.processEvents()
                time.sleep(0.01)
            
            # 验证结果
            self.assertEqual(len(self.errors), 0, f"并发任务出错: {self.errors}")
            self.assertEqual(len(self.results), task_count, f"应该有{task_count}个结果")
            
            # 验证每个结果
            for result in self.results:
                self.assertEqual(result['content'], result['expected'])
        
        finally:
            # 清理临时文件
            for file_name, _ in test_files:
                if os.path.exists(file_name):
                    os.remove(file_name)
    
    def test_thread_pool_stats(self):
        """测试线程池统计"""
        stats = get_thread_pool_stats()
        
        self.assertIn('max_thread_count', stats)
        self.assertIn('active_thread_count', stats)
        self.assertIn('expiry_timeout', stats)
        
        self.assertGreater(stats['max_thread_count'], 0)
        self.assertGreaterEqual(stats['active_thread_count'], 0)


class TestCPUTasks(unittest.TestCase):
    """CPU任务测试"""
    
    def setUp(self):
        """测试设置"""
        self.app = QtWidgets.QApplication.instance()
        if self.app is None:
            self.app = QtWidgets.QApplication([])
        
        self.logger = get_logger()
        self.results = []
        self.errors = []
        
        # 确保CPU管理器已启动
        manager = get_global_cpu_manager()
        if not manager._started:
            manager.start()
    
    def tearDown(self):
        """测试清理"""
        # 等待所有CPU任务完成
        manager = get_global_cpu_manager()
        start_time = time.time()
        while manager.get_active_task_count() > 0 and time.time() - start_time < 10:
            self.app.processEvents()
            time.sleep(0.1)
    
    def test_fibonacci_calculation(self):
        """测试斐波那契计算"""
        n = 30
        
        def on_success(task_id, result):
            self.results.append(result)
        
        def on_error(task_id, error, exc):
            self.errors.append(error)
        
        submit_cpu(cpu_intensive_calculation, args=(n,), 
                  on_success=on_success, on_error=on_error)
        
        # 等待任务完成
        start_time = time.time()
        while not self.results and not self.errors and time.time() - start_time < 10:
            self.app.processEvents()
            time.sleep(0.01)
        
        # 验证结果
        self.assertEqual(len(self.errors), 0, f"CPU任务出错: {self.errors}")
        self.assertEqual(len(self.results), 1, "应该有一个结果")
        
        result = self.results[0]
        self.assertEqual(result['input'], n)
        self.assertIn('result', result)
        self.assertIn('execution_time', result)
        self.assertGreater(result['execution_time'], 0)
    
    def test_matrix_computation(self):
        """测试矩阵计算"""
        matrix_size = 100  # 使用较小的矩阵以加快测试
        
        def on_success(task_id, result):
            self.results.append(result)
        
        def on_error(task_id, error, exc):
            self.errors.append(error)
        
        submit_cpu(mathematical_computation, args=(matrix_size,),
                  on_success=on_success, on_error=on_error)
        
        # 等待任务完成
        start_time = time.time()
        while not self.results and not self.errors and time.time() - start_time < 10:
            self.app.processEvents()
            time.sleep(0.01)
        
        # 验证结果
        self.assertEqual(len(self.errors), 0, f"矩阵计算出错: {self.errors}")
        self.assertEqual(len(self.results), 1, "应该有一个结果")
        
        result = self.results[0]
        self.assertEqual(result['matrix_size'], matrix_size)
        self.assertIn('result_shape', result)
        self.assertIn('execution_time', result)
    
    def test_concurrent_cpu_tasks(self):
        """测试并发CPU任务"""
        task_count = 3
        
        # 提交多个CPU任务
        for i in range(task_count):
            n = 25 + i  # 不同的斐波那契数
            
            def on_success(task_id, result, expected_n=n):
                result['expected_n'] = expected_n
                self.results.append(result)
            
            def on_error(task_id, error, exc):
                self.errors.append(error)
            
            submit_cpu(cpu_intensive_calculation, args=(n,),
                      on_success=on_success, on_error=on_error)
        
        # 等待所有任务完成
        start_time = time.time()
        while len(self.results) + len(self.errors) < task_count and time.time() - start_time < 20:
            self.app.processEvents()
            time.sleep(0.1)
        
        # 验证结果
        self.assertEqual(len(self.errors), 0, f"并发CPU任务出错: {self.errors}")
        self.assertEqual(len(self.results), task_count, f"应该有{task_count}个结果")
        
        # 验证每个结果
        for result in self.results:
            self.assertEqual(result['input'], result['expected_n'])
            self.assertIn('result', result)
    
    def test_cpu_stats(self):
        """测试CPU统计"""
        stats = get_cpu_stats()
        
        self.assertIn('max_workers', stats)
        self.assertIn('active_tasks', stats)
        self.assertIn('queue_size', stats)
        self.assertIn('started', stats)
        
        self.assertGreater(stats['max_workers'], 0)
        self.assertGreaterEqual(stats['active_tasks'], 0)
        self.assertTrue(stats['started'])


class TestAsyncTasks(unittest.TestCase):
    """异步任务测试"""
    
    def setUp(self):
        """测试设置"""
        if not QASYNC_AVAILABLE:
            self.skipTest("qasync不可用")
        
        self.app = QtWidgets.QApplication.instance()
        if self.app is None:
            self.app = QtWidgets.QApplication([])
        
        self.logger = get_logger()
        self.results = []
        self.errors = []
        
        # 设置异步事件循环
        try:
            self.loop = setup_qasync_event_loop(self.app)
        except Exception as e:
            self.skipTest(f"qasync设置失败: {e}")
    
    def test_async_http_request(self):
        """测试异步HTTP请求"""
        url = "https://httpbin.org/get"
        
        def on_success(task_id, result):
            self.results.append(result)
        
        def on_error(task_id, error, exc):
            self.errors.append(error)
        
        submit_async_http(url, on_success=on_success, on_error=on_error)
        
        # 等待任务完成
        start_time = time.time()
        while not self.results and not self.errors and time.time() - start_time < 10:
            self.app.processEvents()
            time.sleep(0.01)
        
        # 验证结果
        if self.errors:
            self.skipTest(f"网络请求失败，可能是网络问题: {self.errors[0]}")
        
        self.assertEqual(len(self.results), 1, "应该有一个结果")
        self.assertEqual(self.results[0]['status_code'], 200)
    
    def test_async_stats(self):
        """测试异步统计"""
        stats = get_async_stats()
        
        self.assertIn('active_tasks', stats)
        self.assertIn('qasync_available', stats)
        self.assertIn('event_loop_set', stats)
        
        self.assertTrue(stats['qasync_available'])
        self.assertTrue(stats['event_loop_set'])


class TestPerformanceProfiler(unittest.TestCase):
    """性能分析器测试"""
    
    def setUp(self):
        """测试设置"""
        self.app = QtWidgets.QApplication.instance()
        if self.app is None:
            self.app = QtWidgets.QApplication([])
        
        self.profiler = get_global_profiler()
        self.profiler.clear_records()
    
    def test_performance_measurement(self):
        """测试性能测量"""
        @measure_performance("test_operation", "default")
        def test_function():
            time.sleep(0.1)  # 模拟耗时操作
            return "test_result"
        
        result = test_function()
        
        self.assertEqual(result, "test_result")
        
        # 检查性能记录
        stats = self.profiler.get_stats("test_operation")
        self.assertEqual(len(stats), 1)
        
        stat = stats[0]
        self.assertEqual(stat.operation_name, "test_operation")
        self.assertEqual(stat.total_calls, 1)
        self.assertGreaterEqual(stat.avg_duration_ms, 100)  # 至少100ms
    
    def test_milestone_recording(self):
        """测试里程碑记录"""
        milestone_name = "test_milestone"
        record_milestone(milestone_name)
        
        milestones = self.profiler.get_milestones()
        self.assertIn(milestone_name, milestones)
        self.assertGreater(milestones[milestone_name], 0)
    
    def test_performance_warning(self):
        """测试性能警告"""
        warnings = []
        
        def on_warning(operation_name, duration_ms):
            warnings.append((operation_name, duration_ms))
        
        self.profiler.performance_warning.connect(on_warning)
        
        # 设置较低的阈值
        self.profiler.warning_thresholds['test'] = 50
        
        @measure_performance("slow_operation", "test")
        def slow_function():
            time.sleep(0.1)  # 100ms，超过50ms阈值
        
        slow_function()
        
        # 处理事件
        self.app.processEvents()
        
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0][0], "slow_operation")
        self.assertGreaterEqual(warnings[0][1], 100)


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestIOTasks))
    suite.addTests(loader.loadTestsFromTestCase(TestCPUTasks))
    suite.addTests(loader.loadTestsFromTestCase(TestAsyncTasks))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceProfiler))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    # Windows平台multiprocessing保护
    if sys.platform.startswith('win'):
        import multiprocessing
        multiprocessing.freeze_support()
    
    success = run_tests()
    sys.exit(0 if success else 1)

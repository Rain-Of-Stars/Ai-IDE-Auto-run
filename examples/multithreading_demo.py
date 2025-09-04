# -*- coding: utf-8 -*-
"""
多线程架构演示程序

展示新的多线程架构的使用方法：
1. 并发下载N个URL并在ListView展示摘要
2. CPU密集计算（如大循环/图像滤波）并发执行，结果顺序正确回显
3. 异步网络请求处理
4. 性能监控和分析
"""

import sys
import os
import time
import random
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import QTimer

# 导入多线程模块
from workers.io_tasks import submit_io, HTTPRequestTask, get_thread_pool_stats
from workers.cpu_tasks import submit_cpu, get_cpu_stats, cpu_intensive_calculation, mathematical_computation
from workers.async_tasks import (setup_qasync_event_loop, submit_async_http, 
                                submit_async_batch_requests, get_async_stats, QASYNC_AVAILABLE)

# 导入性能分析器
from utils.performance_profiler import get_global_profiler, measure_performance, record_milestone

from auto_approve.logger_manager import get_logger


class MultithreadingDemo(QtWidgets.QMainWindow):
    """多线程演示主窗口"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger()
        self.profiler = get_global_profiler()
        
        # 记录启动里程碑
        record_milestone("demo_window_init_start")
        
        self.setWindowTitle("多线程架构演示")
        self.setGeometry(100, 100, 1000, 700)
        
        # 创建UI
        self._create_ui()
        
        # 连接性能监控信号
        self.profiler.performance_warning.connect(self._on_performance_warning)
        
        # 任务计数器
        self.download_tasks = {}
        self.cpu_tasks = {}
        self.async_tasks = {}
        
        # 统计定时器
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(1000)  # 每秒更新统计
        
        record_milestone("demo_window_init_complete")
    
    def _create_ui(self):
        """创建用户界面"""
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QtWidgets.QVBoxLayout(central_widget)
        
        # 标题
        title_label = QtWidgets.QLabel("多线程架构演示")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # 创建选项卡
        tab_widget = QtWidgets.QTabWidget()
        layout.addWidget(tab_widget)
        
        # IO任务选项卡
        io_tab = self._create_io_tab()
        tab_widget.addTab(io_tab, "IO任务演示")
        
        # CPU任务选项卡
        cpu_tab = self._create_cpu_tab()
        tab_widget.addTab(cpu_tab, "CPU任务演示")
        
        # 异步任务选项卡
        async_tab = self._create_async_tab()
        tab_widget.addTab(async_tab, "异步任务演示")
        
        # 性能监控选项卡
        perf_tab = self._create_performance_tab()
        tab_widget.addTab(perf_tab, "性能监控")
        
        # 状态栏
        self.statusBar().showMessage("就绪")
    
    def _create_io_tab(self) -> QtWidgets.QWidget:
        """创建IO任务演示选项卡"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # 控制区域
        control_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(control_layout)
        
        # URL输入
        self.url_input = QtWidgets.QLineEdit()
        self.url_input.setPlaceholderText("输入URL，多个URL用逗号分隔")
        self.url_input.setText("https://httpbin.org/delay/1,https://httpbin.org/delay/2,https://httpbin.org/json")
        control_layout.addWidget(QtWidgets.QLabel("URLs:"))
        control_layout.addWidget(self.url_input)
        
        # 并发数控制
        self.concurrent_spin = QtWidgets.QSpinBox()
        self.concurrent_spin.setRange(1, 20)
        self.concurrent_spin.setValue(5)
        control_layout.addWidget(QtWidgets.QLabel("并发数:"))
        control_layout.addWidget(self.concurrent_spin)
        
        # 开始按钮
        start_download_btn = QtWidgets.QPushButton("开始并发下载")
        start_download_btn.clicked.connect(self._start_concurrent_downloads)
        control_layout.addWidget(start_download_btn)
        
        # 结果显示
        self.download_list = QtWidgets.QListWidget()
        layout.addWidget(QtWidgets.QLabel("下载结果:"))
        layout.addWidget(self.download_list)
        
        return widget
    
    def _create_cpu_tab(self) -> QtWidgets.QWidget:
        """创建CPU任务演示选项卡"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # 控制区域
        control_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(control_layout)
        
        # 任务类型选择
        self.cpu_task_combo = QtWidgets.QComboBox()
        self.cpu_task_combo.addItems(["斐波那契计算", "矩阵运算", "混合计算"])
        control_layout.addWidget(QtWidgets.QLabel("任务类型:"))
        control_layout.addWidget(self.cpu_task_combo)
        
        # 任务数量
        self.cpu_task_count = QtWidgets.QSpinBox()
        self.cpu_task_count.setRange(1, 20)
        self.cpu_task_count.setValue(5)
        control_layout.addWidget(QtWidgets.QLabel("任务数量:"))
        control_layout.addWidget(self.cpu_task_count)
        
        # 开始按钮
        start_cpu_btn = QtWidgets.QPushButton("开始CPU计算")
        start_cpu_btn.clicked.connect(self._start_cpu_tasks)
        control_layout.addWidget(start_cpu_btn)
        
        # 结果显示
        self.cpu_list = QtWidgets.QListWidget()
        layout.addWidget(QtWidgets.QLabel("计算结果:"))
        layout.addWidget(self.cpu_list)
        
        return widget
    
    def _create_async_tab(self) -> QtWidgets.QWidget:
        """创建异步任务演示选项卡"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        if not QASYNC_AVAILABLE:
            layout.addWidget(QtWidgets.QLabel("qasync不可用，请安装: pip install qasync"))
            return widget
        
        # 控制区域
        control_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(control_layout)
        
        # API列表
        self.api_input = QtWidgets.QLineEdit()
        self.api_input.setPlaceholderText("输入API URL，多个用逗号分隔")
        self.api_input.setText("https://httpbin.org/get,https://httpbin.org/user-agent,https://httpbin.org/headers")
        control_layout.addWidget(QtWidgets.QLabel("APIs:"))
        control_layout.addWidget(self.api_input)
        
        # 开始按钮
        start_async_btn = QtWidgets.QPushButton("开始异步请求")
        start_async_btn.clicked.connect(self._start_async_requests)
        control_layout.addWidget(start_async_btn)
        
        # 结果显示
        self.async_list = QtWidgets.QListWidget()
        layout.addWidget(QtWidgets.QLabel("异步请求结果:"))
        layout.addWidget(self.async_list)
        
        return widget
    
    def _create_performance_tab(self) -> QtWidgets.QWidget:
        """创建性能监控选项卡"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # 统计显示
        stats_layout = QtWidgets.QGridLayout()
        layout.addLayout(stats_layout)
        
        # IO线程池统计
        stats_layout.addWidget(QtWidgets.QLabel("IO线程池统计:"), 0, 0)
        self.io_stats_label = QtWidgets.QLabel("未知")
        stats_layout.addWidget(self.io_stats_label, 0, 1)
        
        # CPU进程池统计
        stats_layout.addWidget(QtWidgets.QLabel("CPU进程池统计:"), 1, 0)
        self.cpu_stats_label = QtWidgets.QLabel("未知")
        stats_layout.addWidget(self.cpu_stats_label, 1, 1)
        
        # 异步任务统计
        stats_layout.addWidget(QtWidgets.QLabel("异步任务统计:"), 2, 0)
        self.async_stats_label = QtWidgets.QLabel("未知")
        stats_layout.addWidget(self.async_stats_label, 2, 1)
        
        # 性能记录
        layout.addWidget(QtWidgets.QLabel("性能记录:"))
        self.perf_list = QtWidgets.QListWidget()
        layout.addWidget(self.perf_list)
        
        # 导出按钮
        export_btn = QtWidgets.QPushButton("导出性能报告")
        export_btn.clicked.connect(self._export_performance_report)
        layout.addWidget(export_btn)
        
        return widget
    
    @measure_performance("concurrent_downloads", "network")
    def _start_concurrent_downloads(self):
        """开始并发下载"""
        urls = [url.strip() for url in self.url_input.text().split(',') if url.strip()]
        if not urls:
            QtWidgets.QMessageBox.warning(self, "警告", "请输入至少一个URL")
            return
        
        self.download_list.clear()
        self.download_tasks.clear()
        
        self.statusBar().showMessage(f"开始下载 {len(urls)} 个URL...")
        
        for i, url in enumerate(urls):
            task_id = f"download_{i}"
            self.download_tasks[task_id] = {
                'url': url,
                'start_time': time.time(),
                'status': 'pending'
            }
            
            # 创建HTTP请求任务
            task = HTTPRequestTask(url, task_id=task_id)
            submit_io(
                task,
                on_success=lambda tid, result, task_id=task_id: self._on_download_success(task_id, result),
                on_error=lambda tid, error, exc, task_id=task_id: self._on_download_error(task_id, error)
            )
    
    def _on_download_success(self, task_id: str, result: Dict[str, Any]):
        """下载成功回调"""
        if task_id in self.download_tasks:
            task_info = self.download_tasks[task_id]
            task_info['status'] = 'success'
            task_info['result'] = result
            
            duration = time.time() - task_info['start_time']
            
            item_text = f"✅ {task_info['url']} - {result['status_code']} ({duration:.2f}s)"
            self.download_list.addItem(item_text)
            
            self._check_downloads_complete()
    
    def _on_download_error(self, task_id: str, error: str):
        """下载失败回调"""
        if task_id in self.download_tasks:
            task_info = self.download_tasks[task_id]
            task_info['status'] = 'error'
            task_info['error'] = error
            
            duration = time.time() - task_info['start_time']
            
            item_text = f"❌ {task_info['url']} - 错误: {error} ({duration:.2f}s)"
            self.download_list.addItem(item_text)
            
            self._check_downloads_complete()
    
    def _check_downloads_complete(self):
        """检查下载是否全部完成"""
        completed = sum(1 for task in self.download_tasks.values() 
                       if task['status'] in ['success', 'error'])
        total = len(self.download_tasks)
        
        if completed == total:
            self.statusBar().showMessage(f"下载完成: {completed}/{total}")
    
    @measure_performance("cpu_tasks", "cpu_task")
    def _start_cpu_tasks(self):
        """开始CPU任务"""
        task_type = self.cpu_task_combo.currentText()
        task_count = self.cpu_task_count.value()
        
        self.cpu_list.clear()
        self.cpu_tasks.clear()
        
        self.statusBar().showMessage(f"开始 {task_count} 个{task_type}任务...")
        
        for i in range(task_count):
            task_id = f"cpu_{i}"
            self.cpu_tasks[task_id] = {
                'type': task_type,
                'start_time': time.time(),
                'status': 'pending'
            }
            
            # 根据类型选择任务
            if task_type == "斐波那契计算":
                n = random.randint(30, 35)  # 随机斐波那契数
                submit_cpu(
                    cpu_intensive_calculation,
                    args=(n,),
                    task_id=task_id,
                    on_success=lambda tid, result, task_id=task_id: self._on_cpu_success(task_id, result),
                    on_error=lambda tid, error, exc, task_id=task_id: self._on_cpu_error(task_id, error)
                )
            elif task_type == "矩阵运算":
                size = random.randint(500, 800)  # 随机矩阵大小
                submit_cpu(
                    mathematical_computation,
                    args=(size,),
                    task_id=task_id,
                    on_success=lambda tid, result, task_id=task_id: self._on_cpu_success(task_id, result),
                    on_error=lambda tid, error, exc, task_id=task_id: self._on_cpu_error(task_id, error)
                )
    
    def _on_cpu_success(self, task_id: str, result: Dict[str, Any]):
        """CPU任务成功回调"""
        if task_id in self.cpu_tasks:
            task_info = self.cpu_tasks[task_id]
            task_info['status'] = 'success'
            task_info['result'] = result
            
            duration = time.time() - task_info['start_time']
            
            item_text = f"✅ {task_info['type']} - 耗时: {result.get('execution_time', 0):.3f}s (总计: {duration:.2f}s)"
            self.cpu_list.addItem(item_text)
            
            self._check_cpu_tasks_complete()
    
    def _on_cpu_error(self, task_id: str, error: str):
        """CPU任务失败回调"""
        if task_id in self.cpu_tasks:
            task_info = self.cpu_tasks[task_id]
            task_info['status'] = 'error'
            task_info['error'] = error
            
            duration = time.time() - task_info['start_time']
            
            item_text = f"❌ {task_info['type']} - 错误: {error} ({duration:.2f}s)"
            self.cpu_list.addItem(item_text)
            
            self._check_cpu_tasks_complete()
    
    def _check_cpu_tasks_complete(self):
        """检查CPU任务是否全部完成"""
        completed = sum(1 for task in self.cpu_tasks.values() 
                       if task['status'] in ['success', 'error'])
        total = len(self.cpu_tasks)
        
        if completed == total:
            self.statusBar().showMessage(f"CPU任务完成: {completed}/{total}")
    
    def _start_async_requests(self):
        """开始异步请求"""
        if not QASYNC_AVAILABLE:
            QtWidgets.QMessageBox.warning(self, "警告", "qasync不可用")
            return
        
        urls = [url.strip() for url in self.api_input.text().split(',') if url.strip()]
        if not urls:
            QtWidgets.QMessageBox.warning(self, "警告", "请输入至少一个API URL")
            return
        
        self.async_list.clear()
        
        self.statusBar().showMessage(f"开始异步请求 {len(urls)} 个API...")
        
        # 提交批量异步请求
        submit_async_batch_requests(
            urls,
            on_success=self._on_async_success,
            on_error=self._on_async_error
        )
    
    def _on_async_success(self, task_id: str, results: List[Dict[str, Any]]):
        """异步请求成功回调"""
        for result in results:
            if 'error' in result:
                item_text = f"❌ {result['url']} - 错误: {result['error']}"
            else:
                item_text = f"✅ {result['url']} - {result.get('status_code', 'N/A')} ({result.get('execution_time', 0):.2f}s)"
            
            self.async_list.addItem(item_text)
        
        self.statusBar().showMessage(f"异步请求完成: {len(results)} 个")
    
    def _on_async_error(self, task_id: str, error: str):
        """异步请求失败回调"""
        item_text = f"❌ 批量请求失败: {error}"
        self.async_list.addItem(item_text)
        self.statusBar().showMessage("异步请求失败")
    
    def _update_stats(self):
        """更新统计信息"""
        # IO线程池统计
        io_stats = get_thread_pool_stats()
        io_text = f"最大线程: {io_stats['max_thread_count']}, 活跃: {io_stats['active_thread_count']}"
        self.io_stats_label.setText(io_text)
        
        # CPU进程池统计
        cpu_stats = get_cpu_stats()
        cpu_text = f"最大进程: {cpu_stats['max_workers']}, 活跃: {cpu_stats['active_tasks']}, 队列: {cpu_stats['queue_size']}"
        self.cpu_stats_label.setText(cpu_text)
        
        # 异步任务统计
        if QASYNC_AVAILABLE:
            async_stats = get_async_stats()
            async_text = f"活跃任务: {async_stats['active_tasks']}, 事件循环: {'是' if async_stats['event_loop_set'] else '否'}"
        else:
            async_text = "不可用"
        self.async_stats_label.setText(async_text)
    
    def _on_performance_warning(self, operation_name: str, duration_ms: float):
        """性能警告处理"""
        item_text = f"⚠️ 性能警告: {operation_name} 耗时 {duration_ms:.1f}ms"
        self.perf_list.addItem(item_text)
        
        # 保持列表长度
        if self.perf_list.count() > 100:
            self.perf_list.takeItem(0)
    
    def _export_performance_report(self):
        """导出性能报告"""
        from utils.performance_profiler import export_performance_report
        
        try:
            file_path = export_performance_report()
            QtWidgets.QMessageBox.information(self, "成功", f"性能报告已导出: {file_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"导出失败: {e}")


def main():
    """主函数"""
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("多线程架构演示")
    
    # 记录应用启动里程碑
    record_milestone("app_start")
    
    # 设置qasync事件循环（如果可用）
    if QASYNC_AVAILABLE:
        try:
            loop = setup_qasync_event_loop(app)
            print("✅ qasync事件循环已设置")
        except Exception as e:
            print(f"⚠️ qasync设置失败: {e}")
    else:
        print("⚠️ qasync不可用，异步功能将被禁用")
    
    # 创建主窗口
    window = MultithreadingDemo()
    window.show()
    
    # 记录窗口显示里程碑
    record_milestone("window_shown")
    
    # 启动应用
    if QASYNC_AVAILABLE:
        import qasync
        with qasync.QEventLoop(app) as loop:
            loop.run_forever()
    else:
        sys.exit(app.exec())


if __name__ == "__main__":
    # Windows平台multiprocessing保护
    if sys.platform.startswith('win'):
        import multiprocessing
        multiprocessing.freeze_support()

    main()

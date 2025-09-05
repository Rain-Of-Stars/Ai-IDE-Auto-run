# -*- coding: utf-8 -*-
"""
GUI响应性测试
验证GUI响应性优化的效果
"""
import os
import sys
import time
import threading
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import QTimer, QElapsedTimer

from auto_approve.gui_responsiveness_manager import get_gui_responsiveness_manager, schedule_ui_update
from auto_approve.gui_performance_monitor import get_gui_performance_monitor, start_gui_monitoring, record_ui_update
from auto_approve.logger_manager import get_logger


class GuiResponsivenessTest(QtWidgets.QWidget):
    """GUI响应性测试窗口"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger()
        self.test_results: List[Dict[str, Any]] = []
        
        # 初始化GUI响应性管理器和性能监控
        self.gui_manager = get_gui_responsiveness_manager()
        self.performance_monitor = get_gui_performance_monitor()
        
        # 连接信号
        self.performance_monitor.performance_alert.connect(self._on_performance_alert)
        self.performance_monitor.responsiveness_changed.connect(self._on_responsiveness_changed)
        self.performance_monitor.metrics_updated.connect(self._on_metrics_updated)
        
        # 启动性能监控
        start_gui_monitoring()
        
        self._setup_ui()
        self._setup_tests()
        
        self.logger.info("GUI响应性测试初始化完成")
    
    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("GUI响应性测试")
        self.setGeometry(100, 100, 800, 600)
        
        layout = QtWidgets.QVBoxLayout()
        
        # 标题
        title = QtWidgets.QLabel("GUI响应性测试")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # 测试控制按钮
        button_layout = QtWidgets.QHBoxLayout()
        
        self.btn_start_test = QtWidgets.QPushButton("开始测试")
        self.btn_start_test.clicked.connect(self.start_tests)
        button_layout.addWidget(self.btn_start_test)
        
        self.btn_stress_test = QtWidgets.QPushButton("压力测试")
        self.btn_stress_test.clicked.connect(self.start_stress_test)
        button_layout.addWidget(self.btn_stress_test)
        
        self.btn_clear_results = QtWidgets.QPushButton("清空结果")
        self.btn_clear_results.clicked.connect(self.clear_results)
        button_layout.addWidget(self.btn_clear_results)
        
        layout.addLayout(button_layout)
        
        # 实时性能指标显示
        metrics_group = QtWidgets.QGroupBox("实时性能指标")
        metrics_layout = QtWidgets.QGridLayout()
        
        self.lbl_cpu = QtWidgets.QLabel("CPU使用率: --")
        self.lbl_memory = QtWidgets.QLabel("内存使用: --")
        self.lbl_response_time = QtWidgets.QLabel("响应时间: --")
        self.lbl_ui_updates = QtWidgets.QLabel("UI更新频率: --")
        self.lbl_responsiveness = QtWidgets.QLabel("响应状态: --")
        
        metrics_layout.addWidget(self.lbl_cpu, 0, 0)
        metrics_layout.addWidget(self.lbl_memory, 0, 1)
        metrics_layout.addWidget(self.lbl_response_time, 1, 0)
        metrics_layout.addWidget(self.lbl_ui_updates, 1, 1)
        metrics_layout.addWidget(self.lbl_responsiveness, 2, 0, 1, 2)
        
        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group)
        
        # 测试结果显示
        results_group = QtWidgets.QGroupBox("测试结果")
        results_layout = QtWidgets.QVBoxLayout()
        
        self.text_results = QtWidgets.QTextEdit()
        self.text_results.setMaximumHeight(200)
        results_layout.addWidget(self.text_results)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        # 测试进度
        self.progress_bar = QtWidgets.QProgressBar()
        layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)
    
    def _setup_tests(self):
        """设置测试"""
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self._run_next_test)
        
        self.current_test_index = 0
        self.test_start_time = 0.0
        self.test_running = False
        
        # 定义测试用例
        self.test_cases = [
            {"name": "基础响应性测试", "duration": 5, "method": self._test_basic_responsiveness},
            {"name": "UI更新批处理测试", "duration": 10, "method": self._test_ui_batching},
            {"name": "高频更新测试", "duration": 8, "method": self._test_high_frequency_updates},
            {"name": "内存使用测试", "duration": 6, "method": self._test_memory_usage},
            {"name": "线程池负载测试", "duration": 12, "method": self._test_thread_pool_load}
        ]
    
    def start_tests(self):
        """开始测试"""
        if self.test_running:
            return
        
        self.test_running = True
        self.current_test_index = 0
        self.test_results.clear()
        self.text_results.clear()
        
        self.btn_start_test.setEnabled(False)
        self.btn_stress_test.setEnabled(False)
        
        self.progress_bar.setMaximum(len(self.test_cases))
        self.progress_bar.setValue(0)
        
        self.logger.info("开始GUI响应性测试")
        self._run_next_test()
    
    def _run_next_test(self):
        """运行下一个测试"""
        if self.current_test_index >= len(self.test_cases):
            self._finish_tests()
            return
        
        test_case = self.test_cases[self.current_test_index]
        self.logger.info(f"开始测试: {test_case['name']}")
        
        # 更新进度
        self.progress_bar.setValue(self.current_test_index)
        
        # 记录测试开始时间
        self.test_start_time = time.time()
        
        # 运行测试
        test_case['method']()
        
        # 设置测试持续时间
        QTimer.singleShot(test_case['duration'] * 1000, self._finish_current_test)
    
    def _finish_current_test(self):
        """完成当前测试"""
        test_case = self.test_cases[self.current_test_index]
        test_duration = time.time() - self.test_start_time
        
        # 收集测试结果
        metrics = self.performance_monitor.get_current_metrics()
        summary = self.performance_monitor.get_performance_summary()
        
        result = {
            'test_name': test_case['name'],
            'duration': test_duration,
            'metrics': metrics,
            'summary': summary,
            'timestamp': time.time()
        }
        
        self.test_results.append(result)
        
        # 显示结果
        self._display_test_result(result)
        
        self.logger.info(f"完成测试: {test_case['name']}")
        
        # 进入下一个测试
        self.current_test_index += 1
        QTimer.singleShot(1000, self._run_next_test)  # 1秒间隔
    
    def _finish_tests(self):
        """完成所有测试"""
        self.test_running = False
        self.progress_bar.setValue(len(self.test_cases))
        
        self.btn_start_test.setEnabled(True)
        self.btn_stress_test.setEnabled(True)
        
        # 生成总结报告
        self._generate_summary_report()
        
        self.logger.info("GUI响应性测试完成")
    
    def _test_basic_responsiveness(self):
        """基础响应性测试"""
        # 模拟正常的UI更新
        def update_ui():
            for i in range(50):
                schedule_ui_update(
                    widget_id=f'test_widget_{i}',
                    update_type='tooltip',
                    data={'text': f'测试更新 {i}'},
                    priority=1
                )
                time.sleep(0.1)
        
        # 在后台线程运行
        threading.Thread(target=update_ui, daemon=True).start()
    
    def _test_ui_batching(self):
        """UI更新批处理测试"""
        # 快速连续的UI更新，测试批处理效果
        def batch_updates():
            for batch in range(10):
                for i in range(20):
                    schedule_ui_update(
                        widget_id=f'batch_widget_{i}',
                        update_type='status',
                        data={'status': f'批次 {batch}, 更新 {i}'},
                        priority=2
                    )
                time.sleep(0.5)
        
        threading.Thread(target=batch_updates, daemon=True).start()
    
    def _test_high_frequency_updates(self):
        """高频更新测试"""
        # 高频率的UI更新，测试系统负载
        def high_freq_updates():
            for i in range(200):
                schedule_ui_update(
                    widget_id='high_freq_widget',
                    update_type='tooltip',
                    data={'text': f'高频更新 {i}'},
                    priority=3
                )
                record_ui_update()
                time.sleep(0.02)  # 50Hz更新频率
        
        threading.Thread(target=high_freq_updates, daemon=True).start()
    
    def _test_memory_usage(self):
        """内存使用测试"""
        # 创建大量UI更新请求，测试内存管理
        def memory_test():
            for i in range(100):
                for j in range(10):
                    schedule_ui_update(
                        widget_id=f'memory_widget_{i}_{j}',
                        update_type='menu',
                        data={'large_data': 'x' * 1000},  # 1KB数据
                        priority=1
                    )
                time.sleep(0.05)
        
        threading.Thread(target=memory_test, daemon=True).start()
    
    def _test_thread_pool_load(self):
        """线程池负载测试"""
        # 模拟线程池高负载情况
        from workers.io_tasks import submit_io, IOTaskBase
        
        class DummyIOTask(IOTaskBase):
            def run(self):
                time.sleep(0.1)  # 模拟IO操作
                return "dummy_result"
        
        def thread_pool_test():
            for i in range(50):
                task = DummyIOTask(f"load_test_{i}")
                submit_io(task)
                time.sleep(0.1)
        
        threading.Thread(target=thread_pool_test, daemon=True).start()
    
    def start_stress_test(self):
        """开始压力测试"""
        self.logger.info("开始GUI压力测试")
        
        # 同时运行多个高负载任务
        self._test_high_frequency_updates()
        self._test_ui_batching()
        self._test_thread_pool_load()
        
        # 10秒后停止
        QTimer.singleShot(10000, lambda: self.logger.info("压力测试完成"))
    
    def clear_results(self):
        """清空测试结果"""
        self.test_results.clear()
        self.text_results.clear()
        self.logger.info("测试结果已清空")
    
    def _display_test_result(self, result: Dict[str, Any]):
        """显示测试结果"""
        text = f"✅ {result['test_name']} (耗时: {result['duration']:.1f}s)\n"
        
        if result['metrics']:
            metrics = result['metrics']
            text += f"   CPU: {metrics.main_thread_cpu_percent:.1f}%, "
            text += f"内存: {metrics.memory_usage_mb:.1f}MB, "
            text += f"响应时间: {metrics.response_time_ms:.1f}ms\n"
        
        if result['summary']:
            summary = result['summary']
            text += f"   平均响应时间: {summary.get('avg_response_time_ms', 0):.1f}ms, "
            text += f"响应率: {summary.get('responsive_ratio', 0):.1%}\n"
        
        text += "\n"
        
        self.text_results.append(text)
    
    def _generate_summary_report(self):
        """生成总结报告"""
        if not self.test_results:
            return
        
        text = "=" * 50 + "\n"
        text += "GUI响应性测试总结报告\n"
        text += "=" * 50 + "\n\n"
        
        # 计算平均指标
        total_tests = len(self.test_results)
        avg_cpu = sum(r['metrics'].main_thread_cpu_percent for r in self.test_results if r['metrics']) / total_tests
        avg_memory = sum(r['metrics'].memory_usage_mb for r in self.test_results if r['metrics']) / total_tests
        avg_response = sum(r['summary'].get('avg_response_time_ms', 0) for r in self.test_results if r['summary']) / total_tests
        
        text += f"测试总数: {total_tests}\n"
        text += f"平均CPU使用率: {avg_cpu:.1f}%\n"
        text += f"平均内存使用: {avg_memory:.1f}MB\n"
        text += f"平均响应时间: {avg_response:.1f}ms\n\n"
        
        # 性能评级
        if avg_response < 100:
            grade = "优秀"
        elif avg_response < 200:
            grade = "良好"
        elif avg_response < 500:
            grade = "一般"
        else:
            grade = "需要优化"
        
        text += f"GUI响应性评级: {grade}\n"
        
        self.text_results.append(text)
    
    def _on_performance_alert(self, alert_type: str, value: float):
        """性能警告处理"""
        self.logger.warning(f"性能警告: {alert_type} = {value}")
    
    def _on_responsiveness_changed(self, is_responsive: bool):
        """响应性状态变化"""
        status = "响应" if is_responsive else "无响应"
        self.lbl_responsiveness.setText(f"响应状态: {status}")
        
        if not is_responsive:
            self.lbl_responsiveness.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.lbl_responsiveness.setStyleSheet("color: green; font-weight: bold;")
    
    def _on_metrics_updated(self, metrics):
        """性能指标更新"""
        if metrics:
            self.lbl_cpu.setText(f"CPU使用率: {metrics.main_thread_cpu_percent:.1f}%")
            self.lbl_memory.setText(f"内存使用: {metrics.memory_usage_mb:.1f}MB")
            self.lbl_response_time.setText(f"响应时间: {metrics.response_time_ms:.1f}ms")
            self.lbl_ui_updates.setText(f"UI更新频率: {metrics.ui_update_count}/s")


def main():
    """主函数"""
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("GUI响应性测试")
    
    # 创建测试窗口
    test_window = GuiResponsivenessTest()
    test_window.show()
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

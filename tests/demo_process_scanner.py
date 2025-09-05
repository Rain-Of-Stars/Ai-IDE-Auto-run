# -*- coding: utf-8 -*-
"""
独立扫描进程演示

演示新的独立扫描进程如何避免UI卡顿
"""

import sys
import time
from pathlib import Path

from PySide6 import QtWidgets, QtCore, QtGui
from auto_approve.config_manager import AppConfig
from auto_approve.logger_manager import get_logger, enable_file_logging
from auto_approve.scanner_process_adapter import ProcessScannerWorker


class ProcessScannerDemo(QtWidgets.QMainWindow):
    """独立扫描进程演示窗口"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger()
        self.scanner_worker = None
        self.setup_ui()
        self.setup_config()
        
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("独立扫描进程演示")
        self.setGeometry(100, 100, 600, 400)
        
        # 中央窗口
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        # 布局
        layout = QtWidgets.QVBoxLayout(central_widget)
        
        # 标题
        title = QtWidgets.QLabel("独立扫描进程演示")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # 说明文本
        info_text = QtWidgets.QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(100)
        info_text.setText(
            "这个演示展示了独立扫描进程的优势：\n"
            "• 扫描功能在独立进程中运行，不会阻塞UI\n"
            "• 即使扫描进程崩溃，主UI仍然响应\n"
            "• 可以在扫描运行时自由操作界面"
        )
        layout.addWidget(info_text)
        
        # 状态显示
        self.status_label = QtWidgets.QLabel("状态: 未启动")
        self.status_label.setStyleSheet("padding: 5px; border: 1px solid gray;")
        layout.addWidget(self.status_label)
        
        # 日志显示
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)
        
        # 按钮区域
        button_layout = QtWidgets.QHBoxLayout()
        
        self.start_btn = QtWidgets.QPushButton("启动扫描进程")
        self.start_btn.clicked.connect(self.start_scanning)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QtWidgets.QPushButton("停止扫描进程")
        self.stop_btn.clicked.connect(self.stop_scanning)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        # UI压力测试按钮
        self.stress_btn = QtWidgets.QPushButton("UI压力测试")
        self.stress_btn.clicked.connect(self.ui_stress_test)
        button_layout.addWidget(self.stress_btn)
        
        layout.addLayout(button_layout)
        
        # 进度条（用于演示UI响应性）
        self.progress_bar = QtWidgets.QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # 定时器用于更新进度条
        self.progress_timer = QtCore.QTimer()
        self.progress_timer.timeout.connect(self.update_progress)
        self.progress_timer.start(100)  # 每100ms更新一次
        self.progress_value = 0
        
    def setup_config(self):
        """设置配置"""
        self.config = AppConfig()
        self.config.interval_ms = 1000
        self.config.threshold = 0.8
        self.config.grayscale = True
        self.config.use_monitor = False
        self.config.window_title = "记事本"
        self.config.click_delay_ms = 500
        self.config.debug_mode = True
        
        # 设置模板路径
        template_dir = Path("templates")
        if template_dir.exists():
            template_files = list(template_dir.glob("*.png"))
            self.config.template_paths = [str(f) for f in template_files[:3]]
        else:
            self.config.template_paths = []
        
        self.log(f"配置已设置，模板数量: {len(self.config.template_paths)}")
    
    def start_scanning(self):
        """启动扫描"""
        try:
            self.scanner_worker = ProcessScannerWorker(self.config)
            
            # 连接信号
            self.scanner_worker.sig_status.connect(self.on_status_update)
            self.scanner_worker.sig_hit.connect(self.on_hit_detected)
            self.scanner_worker.sig_log.connect(self.on_log_message)
            
            # 启动
            self.scanner_worker.start()
            
            # 更新UI
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.status_label.setText("状态: 启动中...")
            
            self.log("扫描进程启动命令已发送")
            
        except Exception as e:
            self.log(f"启动扫描失败: {e}")
            self.logger.error(f"启动扫描失败: {e}")
    
    def stop_scanning(self):
        """停止扫描"""
        try:
            if self.scanner_worker:
                self.scanner_worker.stop()
                self.scanner_worker.cleanup()
                self.scanner_worker = None
            
            # 更新UI
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_label.setText("状态: 已停止")
            
            self.log("扫描进程停止命令已发送")
            
        except Exception as e:
            self.log(f"停止扫描失败: {e}")
            self.logger.error(f"停止扫描失败: {e}")
    
    def ui_stress_test(self):
        """UI压力测试 - 演示即使在高负载下UI仍然响应"""
        self.log("开始UI压力测试...")
        
        # 创建一个计算密集型任务
        def stress_task():
            start_time = time.time()
            count = 0
            while time.time() - start_time < 3:  # 运行3秒
                count += 1
                # 模拟计算
                sum(range(1000))
                
                # 每1000次迭代更新一次UI
                if count % 1000 == 0:
                    QtCore.QCoreApplication.processEvents()
            
            self.log(f"压力测试完成，执行了 {count} 次迭代")
        
        # 在定时器中执行，避免阻塞UI
        QtCore.QTimer.singleShot(100, stress_task)
    
    def update_progress(self):
        """更新进度条 - 演示UI响应性"""
        self.progress_value = (self.progress_value + 1) % 101
        self.progress_bar.setValue(self.progress_value)
    
    def on_status_update(self, status: str):
        """处理状态更新"""
        self.status_label.setText(f"状态: {status}")
        self.log(f"状态更新: {status}")
    
    def on_hit_detected(self, score: float, x: int, y: int):
        """处理命中检测"""
        self.log(f"检测到命中: 置信度={score:.3f}, 位置=({x}, {y})")
    
    def on_log_message(self, message: str):
        """处理日志消息"""
        self.log(f"扫描进程: {message}")
    
    def log(self, message: str):
        """添加日志到界面"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.scanner_worker:
            self.stop_scanning()
        event.accept()


def main():
    """主函数"""
    app = QtWidgets.QApplication(sys.argv)
    
    # 启用日志
    enable_file_logging(True)
    
    # 创建演示窗口
    demo = ProcessScannerDemo()
    demo.show()
    
    # 运行应用
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

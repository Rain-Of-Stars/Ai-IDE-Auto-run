# -*- coding: utf-8 -*-
"""
性能监控器 - 实时监控CPU占用和性能指标
提供性能数据可视化和优化建议
"""
from __future__ import annotations
import time
import psutil
import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from PySide6 import QtWidgets, QtCore, QtGui
from auto_approve.logger_manager import get_logger


@dataclass
class PerformanceMetrics:
    """性能指标数据"""
    timestamp: float
    cpu_percent: float
    memory_mb: float
    scan_time_ms: float
    match_time_ms: float
    template_count: int
    adaptive_interval_ms: int
    fps: float


class PerformanceCollector(QtCore.QObject):
    """性能数据收集器"""
    
    # 性能数据更新信号
    metrics_updated = QtCore.Signal(object)  # PerformanceMetrics
    
    def __init__(self, target_process_name: str = "python.exe"):
        super().__init__()
        self.target_process_name = target_process_name
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._logger = get_logger()
        self._metrics_history: List[PerformanceMetrics] = []
        self._max_history = 60  # 保留1分钟数据，减少内存占用
        
        # 性能基线
        self._baseline_cpu = 0.0
        self._baseline_memory = 0.0
        
    def start_monitoring(self):
        """开始性能监控"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        self._logger.info("性能监控已启动")
    
    def stop_monitoring(self):
        """停止性能监控"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._logger.info("性能监控已停止")
    
    def _monitor_loop(self):
        """监控主循环"""
        while self._running:
            try:
                metrics = self._collect_metrics()
                if metrics:
                    self._metrics_history.append(metrics)
                    # 保持历史记录在合理范围内
                    if len(self._metrics_history) > self._max_history:
                        self._metrics_history = self._metrics_history[-self._max_history:]
                    
                    # 发送更新信号
                    self.metrics_updated.emit(metrics)
                
                time.sleep(5.0)  # 每5秒收集一次，减少监控开销
            except Exception as e:
                self._logger.error(f"性能监控异常: {e}")
                time.sleep(5.0)  # 出错后等待5秒再重试
    
    def _collect_metrics(self) -> Optional[PerformanceMetrics]:
        """收集性能指标 - 优化版本，减少进程遍历开销"""
        try:
            # 缓存当前进程PID，避免重复查找
            if not hasattr(self, '_cached_pid') or not self._is_process_alive(self._cached_pid):
                self._cached_pid = self._find_target_process()

            if not self._cached_pid:
                return None

            target_process = psutil.Process(self._cached_pid)
            
            # 收集CPU和内存数据
            cpu_percent = target_process.cpu_percent()
            memory_mb = target_process.memory_info().rss / 1024 / 1024
            
            # 创建性能指标对象（其他数据需要从扫描器获取）
            metrics = PerformanceMetrics(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                scan_time_ms=0.0,  # 需要从扫描器获取
                match_time_ms=0.0,  # 需要从扫描器获取
                template_count=0,  # 需要从扫描器获取
                adaptive_interval_ms=0,  # 需要从扫描器获取
                fps=0.0  # 计算得出
            )
            
            return metrics
            
        except Exception as e:
            self._logger.warning(f"收集性能指标失败: {e}")
            # 清除缓存的PID，下次重新查找
            if hasattr(self, '_cached_pid'):
                delattr(self, '_cached_pid')
            return None

    def _find_target_process(self) -> Optional[int]:
        """查找目标进程PID"""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if self.target_process_name.lower() in proc.info['name'].lower():
                    return proc.info['pid']
        except Exception:
            pass
        return None

    def _is_process_alive(self, pid: int) -> bool:
        """检查进程是否存活"""
        try:
            proc = psutil.Process(pid)
            return proc.is_running() and self.target_process_name.lower() in proc.name().lower()
        except Exception:
            return False
    
    def get_performance_summary(self) -> Dict[str, float]:
        """获取性能摘要"""
        if not self._metrics_history:
            return {}
        
        recent_metrics = self._metrics_history[-60:]  # 最近1分钟
        
        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_mb for m in recent_metrics) / len(recent_metrics)
        max_cpu = max(m.cpu_percent for m in recent_metrics)
        max_memory = max(m.memory_mb for m in recent_metrics)
        
        return {
            'avg_cpu_percent': avg_cpu,
            'max_cpu_percent': max_cpu,
            'avg_memory_mb': avg_memory,
            'max_memory_mb': max_memory,
            'sample_count': len(recent_metrics)
        }


class PerformanceMonitorWidget(QtWidgets.QWidget):
    """性能监控界面组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._logger = get_logger()
        self._collector = PerformanceCollector()
        self._setup_ui()
        self._connect_signals()
        
        # 启动监控
        self._collector.start_monitoring()
    
    def _setup_ui(self):
        """设置界面"""
        self.setWindowTitle("性能监控")
        self.setMinimumSize(600, 400)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # 标题
        title = QtWidgets.QLabel("AI-IDE-Auto-Run 性能监控")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # 实时指标显示
        metrics_group = QtWidgets.QGroupBox("实时性能指标")
        metrics_layout = QtWidgets.QGridLayout(metrics_group)
        
        self.lbl_cpu = QtWidgets.QLabel("CPU使用率: --")
        self.lbl_memory = QtWidgets.QLabel("内存使用: --")
        self.lbl_scan_time = QtWidgets.QLabel("扫描耗时: --")
        self.lbl_match_time = QtWidgets.QLabel("匹配耗时: --")
        self.lbl_interval = QtWidgets.QLabel("自适应间隔: --")
        self.lbl_fps = QtWidgets.QLabel("实际FPS: --")
        
        metrics_layout.addWidget(self.lbl_cpu, 0, 0)
        metrics_layout.addWidget(self.lbl_memory, 0, 1)
        metrics_layout.addWidget(self.lbl_scan_time, 1, 0)
        metrics_layout.addWidget(self.lbl_match_time, 1, 1)
        metrics_layout.addWidget(self.lbl_interval, 2, 0)
        metrics_layout.addWidget(self.lbl_fps, 2, 1)
        
        layout.addWidget(metrics_group)
        
        # 性能建议
        advice_group = QtWidgets.QGroupBox("性能优化建议")
        self.txt_advice = QtWidgets.QTextEdit()
        self.txt_advice.setMaximumHeight(120)
        self.txt_advice.setReadOnly(True)
        advice_layout = QtWidgets.QVBoxLayout(advice_group)
        advice_layout.addWidget(self.txt_advice)
        layout.addWidget(advice_group)
        
        # 控制按钮
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_reset = QtWidgets.QPushButton("重置统计")
        self.btn_export = QtWidgets.QPushButton("导出数据")
        self.btn_close = QtWidgets.QPushButton("关闭")
        
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addWidget(self.btn_export)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)
        
        # 初始建议
        self._update_advice("正在收集性能数据...")
    
    def _connect_signals(self):
        """连接信号"""
        self._collector.metrics_updated.connect(self._on_metrics_updated)
        self.btn_reset.clicked.connect(self._reset_statistics)
        self.btn_export.clicked.connect(self._export_data)
        self.btn_close.clicked.connect(self.close)
    
    def _on_metrics_updated(self, metrics: PerformanceMetrics):
        """更新性能指标显示"""
        try:
            # 更新标签
            self.lbl_cpu.setText(f"CPU使用率: {metrics.cpu_percent:.1f}%")
            self.lbl_memory.setText(f"内存使用: {metrics.memory_mb:.1f} MB")
            self.lbl_scan_time.setText(f"扫描耗时: {metrics.scan_time_ms:.1f} ms")
            self.lbl_match_time.setText(f"匹配耗时: {metrics.match_time_ms:.1f} ms")
            self.lbl_interval.setText(f"自适应间隔: {metrics.adaptive_interval_ms} ms")
            self.lbl_fps.setText(f"实际FPS: {metrics.fps:.1f}")
            
            # 根据性能数据生成建议
            self._generate_advice(metrics)
            
        except Exception as e:
            self._logger.error(f"更新性能显示失败: {e}")
    
    def _generate_advice(self, metrics: PerformanceMetrics):
        """生成性能优化建议"""
        advice_lines = []
        
        # CPU使用率建议
        if metrics.cpu_percent > 50:
            advice_lines.append("⚠ CPU使用率较高，建议：")
            advice_lines.append("  • 增加扫描间隔（interval_ms）")
            advice_lines.append("  • 减少模板数量")
            advice_lines.append("  • 关闭多尺度匹配")
        elif metrics.cpu_percent < 10:
            advice_lines.append("✓ CPU使用率良好，可考虑：")
            advice_lines.append("  • 适当减少扫描间隔提高响应速度")
        
        # 内存使用建议
        if metrics.memory_mb > 200:
            advice_lines.append("⚠ 内存使用较高，建议：")
            advice_lines.append("  • 清理模板缓存")
            advice_lines.append("  • 减少调试图片保存")
        
        # 匹配时间建议
        if metrics.match_time_ms > 100:
            advice_lines.append("⚠ 模板匹配耗时较长，建议：")
            advice_lines.append("  • 启用灰度匹配")
            advice_lines.append("  • 设置ROI区域")
            advice_lines.append("  • 优化模板图片尺寸")
        
        if not advice_lines:
            advice_lines.append("✓ 当前性能表现良好")
        
        self._update_advice("\n".join(advice_lines))
    
    def _update_advice(self, text: str):
        """更新建议文本"""
        self.txt_advice.setPlainText(text)
    
    def _reset_statistics(self):
        """重置统计数据"""
        self._collector._metrics_history.clear()
        self._update_advice("统计数据已重置")
    
    def _export_data(self):
        """导出性能数据"""
        try:
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "导出性能数据", "performance_data.csv", "CSV Files (*.csv)"
            )
            if filename:
                self._export_to_csv(filename)
                QtWidgets.QMessageBox.information(self, "导出成功", f"数据已导出到: {filename}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "导出失败", f"导出数据时出错: {e}")
    
    def _export_to_csv(self, filename: str):
        """导出数据到CSV文件"""
        import csv
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # 写入表头
            writer.writerow([
                'timestamp', 'cpu_percent', 'memory_mb', 'scan_time_ms',
                'match_time_ms', 'template_count', 'adaptive_interval_ms', 'fps'
            ])
            # 写入数据
            for metrics in self._collector._metrics_history:
                writer.writerow([
                    metrics.timestamp, metrics.cpu_percent, metrics.memory_mb,
                    metrics.scan_time_ms, metrics.match_time_ms, metrics.template_count,
                    metrics.adaptive_interval_ms, metrics.fps
                ])
    
    def closeEvent(self, event):
        """关闭事件"""
        self._collector.stop_monitoring()
        event.accept()


def show_performance_monitor():
    """显示性能监控窗口"""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    
    monitor = PerformanceMonitorWidget()
    monitor.show()
    return monitor

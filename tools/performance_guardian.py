# -*- coding: utf-8 -*-
"""
性能守则检查系统

提供静态代码扫描和运行时性能监控：
- 自动检测主线程阻塞操作
- 给出重构建议
- 监控关键性能指标
- 生成性能报告
"""

import ast
import os
import re
import time
import threading
import traceback
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import json

from PySide6 import QtCore
from PySide6.QtCore import QObject, Signal, QTimer, QElapsedTimer

from auto_approve.logger_manager import get_logger


@dataclass
class PerformanceIssue:
    """性能问题"""
    file_path: str
    line_number: int
    issue_type: str  # 'blocking_io', 'cpu_intensive', 'long_loop', 'sync_network'
    severity: str    # 'low', 'medium', 'high', 'critical'
    description: str
    suggestion: str
    code_snippet: str


@dataclass
class PerformanceMetric:
    """性能指标"""
    timestamp: float
    operation_name: str
    duration_ms: float
    thread_name: str
    is_main_thread: bool
    memory_usage_mb: float = 0.0
    cpu_percent: float = 0.0


class StaticCodeAnalyzer:
    """静态代码分析器"""
    
    def __init__(self):
        self.logger = get_logger()
        
        # 阻塞操作模式
        self.blocking_patterns = {
            'file_io': [
                r'open\s*\(',
                r'\.read\s*\(',
                r'\.write\s*\(',
                r'\.readline\s*\(',
                r'\.readlines\s*\(',
                r'with\s+open\s*\('
            ],
            'network_io': [
                r'requests\.',
                r'urllib\.',
                r'socket\.',
                r'http\.',
                r'ftp\.',
                r'\.get\s*\(',
                r'\.post\s*\(',
                r'\.put\s*\(',
                r'\.delete\s*\('
            ],
            'cpu_intensive': [
                r'cv2\.',
                r'numpy\.',
                r'np\.',
                r'for\s+\w+\s+in\s+range\s*\(\s*\d{4,}',  # 大循环
                r'while\s+.*:',
                r'\.sort\s*\(',
                r'\.sorted\s*\(',
                r'\.join\s*\(',
                r'\.split\s*\('
            ],
            'database': [
                r'\.execute\s*\(',
                r'\.query\s*\(',
                r'\.commit\s*\(',
                r'\.rollback\s*\(',
                r'cursor\.',
                r'connection\.'
            ]
        }
        
        # Qt主线程相关模式
        self.qt_main_thread_patterns = [
            r'class\s+\w+\s*\(\s*QtWidgets\.',
            r'class\s+\w+\s*\(\s*QWidget',
            r'class\s+\w+\s*\(\s*QMainWindow',
            r'class\s+\w+\s*\(\s*QDialog',
            r'def\s+\w*event\w*\s*\(',
            r'def\s+\w*paint\w*\s*\(',
            r'def\s+\w*mouse\w*\s*\(',
            r'def\s+\w*key\w*\s*\('
        ]
    
    def analyze_file(self, file_path: str) -> List[PerformanceIssue]:
        """分析单个文件"""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # 检查是否是Qt UI相关文件
            is_ui_file = self._is_ui_file(content)
            
            # 逐行分析
            for line_num, line in enumerate(lines, 1):
                line_issues = self._analyze_line(
                    file_path, line_num, line, is_ui_file
                )
                issues.extend(line_issues)
            
            # AST分析
            try:
                tree = ast.parse(content)
                ast_issues = self._analyze_ast(file_path, tree, lines)
                issues.extend(ast_issues)
            except SyntaxError as e:
                self.logger.warning(f"AST解析失败 {file_path}: {e}")
        
        except Exception as e:
            self.logger.error(f"分析文件失败 {file_path}: {e}")
        
        return issues
    
    def _is_ui_file(self, content: str) -> bool:
        """检查是否是UI相关文件"""
        ui_indicators = [
            'QtWidgets', 'QWidget', 'QMainWindow', 'QDialog',
            'QSystemTrayIcon', 'QMenu', 'QAction',
            'paintEvent', 'mousePressEvent', 'keyPressEvent'
        ]
        
        return any(indicator in content for indicator in ui_indicators)
    
    def _analyze_line(self, file_path: str, line_num: int, line: str, 
                     is_ui_file: bool) -> List[PerformanceIssue]:
        """分析单行代码"""
        issues = []
        line_stripped = line.strip()
        
        if not line_stripped or line_stripped.startswith('#'):
            return issues
        
        # 检查阻塞操作
        for category, patterns in self.blocking_patterns.items():
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    severity = 'high' if is_ui_file else 'medium'
                    
                    issue = PerformanceIssue(
                        file_path=file_path,
                        line_number=line_num,
                        issue_type=f'blocking_{category}',
                        severity=severity,
                        description=f'检测到{category}阻塞操作',
                        suggestion=self._get_suggestion(category, is_ui_file),
                        code_snippet=line_stripped
                    )
                    issues.append(issue)
                    break
        
        # 检查Qt主线程操作
        if is_ui_file:
            for pattern in self.qt_main_thread_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # 在UI类中检查是否有阻塞操作
                    for category, patterns in self.blocking_patterns.items():
                        for block_pattern in patterns:
                            if re.search(block_pattern, line, re.IGNORECASE):
                                issue = PerformanceIssue(
                                    file_path=file_path,
                                    line_number=line_num,
                                    issue_type='ui_thread_blocking',
                                    severity='critical',
                                    description=f'UI线程中的{category}阻塞操作',
                                    suggestion='将此操作移至工作线程或使用异步方式',
                                    code_snippet=line_stripped
                                )
                                issues.append(issue)
                                break
                    break
        
        return issues
    
    def _analyze_ast(self, file_path: str, tree: ast.AST, 
                    lines: List[str]) -> List[PerformanceIssue]:
        """AST深度分析"""
        issues = []
        
        class PerformanceVisitor(ast.NodeVisitor):
            def __init__(self, analyzer):
                self.analyzer = analyzer
                self.issues = []
            
            def visit_For(self, node):
                """检查for循环"""
                if hasattr(node.iter, 'func') and hasattr(node.iter.func, 'id'):
                    if node.iter.func.id == 'range':
                        # 检查range参数
                        if (hasattr(node.iter, 'args') and 
                            len(node.iter.args) > 0 and
                            hasattr(node.iter.args[0], 'n') and
                            node.iter.args[0].n > 10000):
                            
                            issue = PerformanceIssue(
                                file_path=file_path,
                                line_number=node.lineno,
                                issue_type='large_loop',
                                severity='medium',
                                description=f'大循环检测: range({node.iter.args[0].n})',
                                suggestion='考虑使用批处理或移至CPU进程池',
                                code_snippet=lines[node.lineno-1].strip() if node.lineno <= len(lines) else ''
                            )
                            self.issues.append(issue)
                
                self.generic_visit(node)
            
            def visit_While(self, node):
                """检查while循环"""
                issue = PerformanceIssue(
                    file_path=file_path,
                    line_number=node.lineno,
                    issue_type='while_loop',
                    severity='low',
                    description='while循环检测',
                    suggestion='确保循环有明确的退出条件，避免无限循环',
                    code_snippet=lines[node.lineno-1].strip() if node.lineno <= len(lines) else ''
                )
                self.issues.append(issue)
                self.generic_visit(node)
        
        visitor = PerformanceVisitor(self)
        visitor.visit(tree)
        issues.extend(visitor.issues)
        
        return issues
    
    def _get_suggestion(self, category: str, is_ui_file: bool) -> str:
        """获取重构建议"""
        suggestions = {
            'file_io': '使用workers.io_tasks模块的submit_io()进行异步文件操作',
            'network_io': '使用workers.async_tasks模块的异步网络请求',
            'cpu_intensive': '使用workers.cpu_tasks模块的submit_cpu()进行CPU密集型计算',
            'database': '使用workers.io_tasks模块进行异步数据库操作'
        }
        
        base_suggestion = suggestions.get(category, '考虑异步处理')
        
        if is_ui_file:
            return f'{base_suggestion}，确保UI线程不被阻塞'
        else:
            return base_suggestion
    
    def analyze_project(self, project_path: str) -> List[PerformanceIssue]:
        """分析整个项目"""
        issues = []
        project_path = Path(project_path)
        
        # 查找Python文件
        python_files = list(project_path.rglob('*.py'))
        
        self.logger.info(f"开始分析项目，共 {len(python_files)} 个Python文件")
        
        for file_path in python_files:
            # 跳过虚拟环境和缓存目录
            if any(part in str(file_path) for part in ['.venv', '__pycache__', '.git']):
                continue
            
            file_issues = self.analyze_file(str(file_path))
            issues.extend(file_issues)
        
        self.logger.info(f"静态分析完成，发现 {len(issues)} 个性能问题")
        return issues


class RuntimePerformanceMonitor(QObject):
    """运行时性能监控器"""
    
    # 性能警告信号
    performance_warning = Signal(str, float)  # operation_name, duration_ms
    # 性能报告信号
    performance_report = Signal(object)  # PerformanceReport
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger()
        self.metrics: List[PerformanceMetric] = []
        self.max_metrics = 1000  # 最多保留1000条记录
        
        # 性能阈值
        self.warning_threshold_ms = 100  # 100ms
        self.critical_threshold_ms = 500  # 500ms
        
        # 监控定时器
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._collect_system_metrics)
        self.monitor_timer.setInterval(5000)  # 每5秒收集一次系统指标
        
        # 主线程ID
        self.main_thread_id = threading.get_ident()
    
    def start_monitoring(self):
        """开始监控"""
        self.monitor_timer.start()
        self.logger.info("运行时性能监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitor_timer.stop()
        self.logger.info("运行时性能监控已停止")
    
    def measure_operation(self, operation_name: str):
        """操作性能测量装饰器"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                timer = QElapsedTimer()
                timer.start()
                
                thread_id = threading.get_ident()
                is_main = thread_id == self.main_thread_id
                
                try:
                    result = func(*args, **kwargs)
                    
                    duration_ms = timer.elapsed()
                    
                    # 记录性能指标
                    metric = PerformanceMetric(
                        timestamp=time.time(),
                        operation_name=operation_name,
                        duration_ms=duration_ms,
                        thread_name=threading.current_thread().name,
                        is_main_thread=is_main
                    )
                    
                    self._add_metric(metric)
                    
                    # 检查性能警告
                    if duration_ms > self.warning_threshold_ms:
                        self._emit_performance_warning(operation_name, duration_ms, is_main)
                    
                    return result
                    
                except Exception as e:
                    duration_ms = timer.elapsed()
                    self.logger.error(f"操作 {operation_name} 异常: {e}, 耗时: {duration_ms}ms")
                    raise
            
            return wrapper
        return decorator
    
    def _add_metric(self, metric: PerformanceMetric):
        """添加性能指标"""
        self.metrics.append(metric)
        
        # 保持指标数量在限制内
        if len(self.metrics) > self.max_metrics:
            self.metrics = self.metrics[-self.max_metrics:]
    
    def _emit_performance_warning(self, operation_name: str, duration_ms: float, is_main_thread: bool):
        """发出性能警告"""
        if is_main_thread and duration_ms > self.critical_threshold_ms:
            self.logger.warning(f"主线程阻塞警告: {operation_name} 耗时 {duration_ms}ms")
        elif duration_ms > self.warning_threshold_ms:
            self.logger.info(f"性能警告: {operation_name} 耗时 {duration_ms}ms")
        
        self.performance_warning.emit(operation_name, duration_ms)
    
    def _collect_system_metrics(self):
        """收集系统性能指标"""
        try:
            import psutil
            
            # 获取当前进程
            process = psutil.Process()
            
            metric = PerformanceMetric(
                timestamp=time.time(),
                operation_name="system_monitor",
                duration_ms=0,
                thread_name="monitor",
                is_main_thread=False,
                memory_usage_mb=process.memory_info().rss / 1024 / 1024,
                cpu_percent=process.cpu_percent()
            )
            
            self._add_metric(metric)
            
        except Exception as e:
            self.logger.error(f"收集系统指标失败: {e}")
    
    def generate_report(self) -> Dict[str, Any]:
        """生成性能报告"""
        if not self.metrics:
            return {'error': '没有性能数据'}
        
        # 按操作分组
        operations = {}
        main_thread_operations = []
        
        for metric in self.metrics:
            op_name = metric.operation_name
            if op_name not in operations:
                operations[op_name] = []
            operations[op_name].append(metric)
            
            if metric.is_main_thread and metric.duration_ms > 0:
                main_thread_operations.append(metric)
        
        # 统计分析
        report = {
            'total_metrics': len(self.metrics),
            'time_range': {
                'start': min(m.timestamp for m in self.metrics),
                'end': max(m.timestamp for m in self.metrics)
            },
            'operations': {},
            'main_thread_warnings': [],
            'recommendations': []
        }
        
        # 操作统计
        for op_name, op_metrics in operations.items():
            durations = [m.duration_ms for m in op_metrics if m.duration_ms > 0]
            if durations:
                report['operations'][op_name] = {
                    'count': len(durations),
                    'avg_duration_ms': sum(durations) / len(durations),
                    'max_duration_ms': max(durations),
                    'min_duration_ms': min(durations)
                }
        
        # 主线程警告
        for metric in main_thread_operations:
            if metric.duration_ms > self.warning_threshold_ms:
                report['main_thread_warnings'].append({
                    'operation': metric.operation_name,
                    'duration_ms': metric.duration_ms,
                    'timestamp': metric.timestamp
                })
        
        # 生成建议
        report['recommendations'] = self._generate_recommendations(report)
        
        return report
    
    def _generate_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """生成性能优化建议"""
        recommendations = []
        
        # 检查主线程阻塞
        if report['main_thread_warnings']:
            recommendations.append(
                f"发现 {len(report['main_thread_warnings'])} 个主线程阻塞操作，"
                "建议将耗时操作移至工作线程"
            )
        
        # 检查慢操作
        slow_operations = []
        for op_name, stats in report['operations'].items():
            if stats['avg_duration_ms'] > self.warning_threshold_ms:
                slow_operations.append(op_name)
        
        if slow_operations:
            recommendations.append(
                f"以下操作平均耗时较长: {', '.join(slow_operations)}，"
                "建议优化或异步处理"
            )
        
        return recommendations


class PerformanceGuardian:
    """性能守护者 - 统一的性能检查接口"""

    def __init__(self):
        self.logger = get_logger()
        self.static_analyzer = StaticCodeAnalyzer()
        self.runtime_monitor = RuntimePerformanceMonitor()

    def check_project(self, project_path: str, output_file: str = None) -> Dict[str, Any]:
        """检查项目性能"""
        self.logger.info(f"开始性能检查: {project_path}")

        # 静态分析
        static_issues = self.static_analyzer.analyze_project(project_path)

        # 生成报告
        report = {
            'project_path': project_path,
            'timestamp': time.time(),
            'static_analysis': {
                'total_issues': len(static_issues),
                'issues_by_severity': self._group_by_severity(static_issues),
                'issues_by_type': self._group_by_type(static_issues),
                'issues': [self._issue_to_dict(issue) for issue in static_issues]
            },
            'recommendations': self._generate_project_recommendations(static_issues)
        }

        # 保存报告
        if output_file:
            self._save_report(report, output_file)

        return report

    def _group_by_severity(self, issues: List[PerformanceIssue]) -> Dict[str, int]:
        """按严重程度分组"""
        severity_count = {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
        for issue in issues:
            severity_count[issue.severity] += 1
        return severity_count

    def _group_by_type(self, issues: List[PerformanceIssue]) -> Dict[str, int]:
        """按类型分组"""
        type_count = {}
        for issue in issues:
            type_count[issue.issue_type] = type_count.get(issue.issue_type, 0) + 1
        return type_count

    def _issue_to_dict(self, issue: PerformanceIssue) -> Dict[str, Any]:
        """将问题转换为字典"""
        return {
            'file_path': issue.file_path,
            'line_number': issue.line_number,
            'issue_type': issue.issue_type,
            'severity': issue.severity,
            'description': issue.description,
            'suggestion': issue.suggestion,
            'code_snippet': issue.code_snippet
        }

    def _generate_project_recommendations(self, issues: List[PerformanceIssue]) -> List[str]:
        """生成项目级别的建议"""
        recommendations = []

        # 统计问题类型
        critical_count = sum(1 for issue in issues if issue.severity == 'critical')
        high_count = sum(1 for issue in issues if issue.severity == 'high')
        ui_blocking_count = sum(1 for issue in issues if issue.issue_type == 'ui_thread_blocking')

        if critical_count > 0:
            recommendations.append(
                f"发现 {critical_count} 个严重性能问题，建议立即处理"
            )

        if ui_blocking_count > 0:
            recommendations.append(
                f"发现 {ui_blocking_count} 个UI线程阻塞问题，"
                "建议使用workers模块进行异步处理"
            )

        if high_count > 5:
            recommendations.append(
                "高优先级问题较多，建议制定性能优化计划"
            )

        # 模块化建议
        io_issues = sum(1 for issue in issues if 'io' in issue.issue_type)
        cpu_issues = sum(1 for issue in issues if 'cpu' in issue.issue_type)

        if io_issues > 0:
            recommendations.append(
                f"发现 {io_issues} 个IO相关问题，建议使用workers.io_tasks模块"
            )

        if cpu_issues > 0:
            recommendations.append(
                f"发现 {cpu_issues} 个CPU密集型问题，建议使用workers.cpu_tasks模块"
            )

        return recommendations

    def _save_report(self, report: Dict[str, Any], output_file: str):
        """保存报告"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self.logger.info(f"性能报告已保存: {output_file}")
        except Exception as e:
            self.logger.error(f"保存报告失败: {e}")


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='性能守则检查工具')
    parser.add_argument('project_path', help='项目路径')
    parser.add_argument('-o', '--output', help='输出报告文件路径')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')

    args = parser.parse_args()

    # 设置日志级别
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)

    # 创建性能守护者
    guardian = PerformanceGuardian()

    # 检查项目
    report = guardian.check_project(args.project_path, args.output)

    # 输出摘要
    print(f"\n性能检查完成: {args.project_path}")
    print(f"总问题数: {report['static_analysis']['total_issues']}")

    severity_stats = report['static_analysis']['issues_by_severity']
    print(f"严重程度分布:")
    for severity, count in severity_stats.items():
        if count > 0:
            print(f"  {severity}: {count}")

    print(f"\n建议:")
    for i, rec in enumerate(report['recommendations'], 1):
        print(f"  {i}. {rec}")

    if args.output:
        print(f"\n详细报告已保存: {args.output}")


if __name__ == "__main__":
    main()

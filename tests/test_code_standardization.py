# -*- coding: utf-8 -*-
"""
代码规范化分析工具：检查代码风格、导入顺序、注释规范等
"""

import os
import ast
import re
from pathlib import Path
from collections import defaultdict, Counter
from typing import Set, Dict, List, Tuple, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent


class CodeStandardizationAnalyzer:
    """代码规范化分析器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.issues = defaultdict(list)  # 问题分类
        self.statistics = defaultdict(int)  # 统计信息
        
        # 编码规范
        self.encoding_patterns = [
            r'# -\*- coding: utf-8 -\*-',
            r'# coding: utf-8',
            r'# coding=utf-8'
        ]
        
        # 导入顺序规范（PEP 8）
        self.import_order = [
            'standard',    # 标准库
            'third_party', # 第三方库
            'local'        # 本地模块
        ]
        
        # 标准库模块
        self.standard_modules = {
            'os', 'sys', 'time', 'datetime', 'json', 'pickle', 'logging',
            'threading', 'multiprocessing', 'queue', 'collections', 'typing',
            'pathlib', 'shutil', 'subprocess', 'signal', 'warnings', 'ctypes',
            'ast', 're', 'uuid', 'traceback', 'hashlib', 'dataclasses',
            'functools', 'itertools', 'operator', 'math', 'random', 'string'
        }
        
        # 第三方库模块
        self.third_party_modules = {
            'PySide6', 'cv2', 'numpy', 'PIL', 'psutil', 'requests', 
            'aiohttp', 'websockets', 'qasync'
        }
    
    def analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """分析单个文件"""
        relative_path = file_path.relative_to(self.project_root)
        file_issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # 检查编码声明
            encoding_issues = self._check_encoding(lines, str(relative_path))
            file_issues.extend(encoding_issues)
            
            # 检查导入顺序
            import_issues = self._check_import_order(content, str(relative_path))
            file_issues.extend(import_issues)
            
            # 检查注释规范
            comment_issues = self._check_comments(lines, str(relative_path))
            file_issues.extend(comment_issues)
            
            # 检查文档字符串
            docstring_issues = self._check_docstrings(content, str(relative_path))
            file_issues.extend(docstring_issues)
            
            # 检查代码风格
            style_issues = self._check_code_style(lines, str(relative_path))
            file_issues.extend(style_issues)
            
            return {
                'file_path': str(relative_path),
                'issues': file_issues,
                'issue_count': len(file_issues)
            }
            
        except Exception as e:
            error_issue = {
                'type': 'file_error',
                'severity': 'error',
                'message': f"无法分析文件: {e}",
                'line': 0
            }
            return {
                'file_path': str(relative_path),
                'issues': [error_issue],
                'issue_count': 1
            }
    
    def _check_encoding(self, lines: List[str], file_path: str) -> List[Dict[str, Any]]:
        """检查编码声明"""
        issues = []
        
        # 检查前两行是否有编码声明
        has_encoding = False
        for i, line in enumerate(lines[:2]):
            for pattern in self.encoding_patterns:
                if re.search(pattern, line):
                    has_encoding = True
                    break
            if has_encoding:
                break
        
        if not has_encoding:
            issues.append({
                'type': 'encoding_missing',
                'severity': 'warning',
                'message': '缺少UTF-8编码声明',
                'line': 1,
                'suggestion': '在文件开头添加: # -*- coding: utf-8 -*-'
            })
        
        return issues
    
    def _check_import_order(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """检查导入顺序（PEP 8）"""
        issues = []
        
        try:
            tree = ast.parse(content)
            imports = []
            
            # 提取所有导入语句
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            module_name = alias.name.split('.')[0]
                            imports.append({
                                'line': node.lineno,
                                'module': module_name,
                                'type': self._classify_import(module_name),
                                'statement': f"import {alias.name}"
                            })
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            module_name = node.module.split('.')[0]
                            imports.append({
                                'line': node.lineno,
                                'module': module_name,
                                'type': self._classify_import(module_name),
                                'statement': f"from {node.module} import ..."
                            })
            
            # 检查导入顺序
            if len(imports) > 1:
                current_type = None
                for imp in imports:
                    if current_type is None:
                        current_type = imp['type']
                    elif self._get_import_order_index(imp['type']) < self._get_import_order_index(current_type):
                        issues.append({
                            'type': 'import_order',
                            'severity': 'info',
                            'message': f"导入顺序不符合PEP 8规范: {imp['statement']}",
                            'line': imp['line'],
                            'suggestion': '按照标准库、第三方库、本地模块的顺序排列导入'
                        })
                    current_type = imp['type']
        
        except SyntaxError:
            pass  # 语法错误由其他工具处理
        
        return issues
    
    def _classify_import(self, module_name: str) -> str:
        """分类导入模块"""
        if module_name in self.standard_modules:
            return 'standard'
        elif module_name in self.third_party_modules:
            return 'third_party'
        elif module_name in ['auto_approve', 'workers', 'capture', 'utils', 'tests', 'tools']:
            return 'local'
        else:
            # 简单判断：小写且不含下划线的可能是第三方库
            if module_name.islower() and '_' not in module_name and len(module_name) > 2:
                return 'third_party'
            return 'local'
    
    def _get_import_order_index(self, import_type: str) -> int:
        """获取导入类型的顺序索引"""
        try:
            return self.import_order.index(import_type)
        except ValueError:
            return len(self.import_order)
    
    def _check_comments(self, lines: List[str], file_path: str) -> List[Dict[str, Any]]:
        """检查注释规范"""
        issues = []
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # 检查中文注释规范
            if '#' in line and not stripped.startswith('#'):
                comment_part = line[line.index('#'):]
                # 检查是否包含中文
                if re.search(r'[\u4e00-\u9fff]', comment_part):
                    # 检查注释前是否有空格
                    if not re.search(r'\s+#', line):
                        issues.append({
                            'type': 'comment_spacing',
                            'severity': 'info',
                            'message': '行内注释前应有两个空格',
                            'line': i,
                            'suggestion': '在#前添加两个空格'
                        })
            
            # 检查TODO/FIXME注释
            if re.search(r'#\s*(TODO|FIXME|XXX|HACK)', stripped, re.IGNORECASE):
                issues.append({
                    'type': 'todo_comment',
                    'severity': 'info',
                    'message': '发现待办事项注释',
                    'line': i,
                    'suggestion': '考虑创建issue跟踪此项目'
                })
        
        return issues
    
    def _check_docstrings(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """检查文档字符串"""
        issues = []
        
        try:
            tree = ast.parse(content)
            
            # 检查模块文档字符串
            if not ast.get_docstring(tree):
                issues.append({
                    'type': 'module_docstring_missing',
                    'severity': 'warning',
                    'message': '缺少模块文档字符串',
                    'line': 1,
                    'suggestion': '在文件开头添加模块说明文档'
                })
            
            # 检查函数和类的文档字符串
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if not ast.get_docstring(node) and not node.name.startswith('_'):
                        issues.append({
                            'type': 'function_docstring_missing',
                            'severity': 'info',
                            'message': f'公共函数 {node.name} 缺少文档字符串',
                            'line': node.lineno,
                            'suggestion': '为公共函数添加文档字符串说明参数和返回值'
                        })
                
                elif isinstance(node, ast.ClassDef):
                    if not ast.get_docstring(node):
                        issues.append({
                            'type': 'class_docstring_missing',
                            'severity': 'info',
                            'message': f'类 {node.name} 缺少文档字符串',
                            'line': node.lineno,
                            'suggestion': '为类添加文档字符串说明其用途'
                        })
        
        except SyntaxError:
            pass
        
        return issues
    
    def _check_code_style(self, lines: List[str], file_path: str) -> List[Dict[str, Any]]:
        """检查代码风格"""
        issues = []
        
        for i, line in enumerate(lines, 1):
            # 检查行长度
            if len(line) > 120:
                issues.append({
                    'type': 'line_too_long',
                    'severity': 'info',
                    'message': f'行长度超过120字符 ({len(line)}字符)',
                    'line': i,
                    'suggestion': '将长行拆分为多行'
                })
            
            # 检查尾随空格
            if line.rstrip() != line and line.strip():
                issues.append({
                    'type': 'trailing_whitespace',
                    'severity': 'info',
                    'message': '行尾有多余空格',
                    'line': i,
                    'suggestion': '删除行尾空格'
                })
            
            # 检查制表符
            if '\t' in line:
                issues.append({
                    'type': 'tab_character',
                    'severity': 'warning',
                    'message': '使用了制表符，应使用空格',
                    'line': i,
                    'suggestion': '将制表符替换为4个空格'
                })
        
        return issues
    
    def analyze_project(self) -> Dict[str, Any]:
        """分析整个项目"""
        python_files = list(self.project_root.rglob('*.py'))
        
        print(f"分析 {len(python_files)} 个Python文件的代码规范...")
        
        all_issues = []
        file_results = []
        
        for file_path in python_files:
            # 跳过虚拟环境和缓存
            if any(part in str(file_path) for part in ['.venv', '__pycache__', '.git']):
                continue
            
            result = self.analyze_file(file_path)
            file_results.append(result)
            all_issues.extend(result['issues'])
        
        # 统计问题类型
        issue_types = Counter(issue['type'] for issue in all_issues)
        severity_counts = Counter(issue['severity'] for issue in all_issues)
        
        return {
            'total_files': len(file_results),
            'total_issues': len(all_issues),
            'issue_types': dict(issue_types),
            'severity_counts': dict(severity_counts),
            'file_results': file_results
        }
    
    def generate_report(self) -> str:
        """生成代码规范化报告"""
        analysis = self.analyze_project()
        
        report = []
        report.append("=" * 60)
        report.append("代码规范化分析报告")
        report.append("=" * 60)
        
        # 总体统计
        report.append(f"\n📊 总体统计:")
        report.append(f"  - 分析文件数: {analysis['total_files']}")
        report.append(f"  - 发现问题数: {analysis['total_issues']}")
        
        # 问题严重程度分布
        report.append(f"\n🚨 问题严重程度:")
        for severity, count in analysis['severity_counts'].items():
            emoji = {'error': '❌', 'warning': '⚠️', 'info': 'ℹ️'}.get(severity, '•')
            report.append(f"  {emoji} {severity}: {count}")
        
        # 问题类型分布
        report.append(f"\n📋 问题类型分布:")
        for issue_type, count in sorted(analysis['issue_types'].items(), key=lambda x: x[1], reverse=True):
            report.append(f"  - {issue_type}: {count}")
        
        # 问题最多的文件
        report.append(f"\n📁 问题最多的文件:")
        file_issues = [(result['file_path'], result['issue_count']) 
                      for result in analysis['file_results']]
        file_issues.sort(key=lambda x: x[1], reverse=True)
        
        for file_path, issue_count in file_issues[:5]:
            if issue_count > 0:
                report.append(f"  - {file_path}: {issue_count} 个问题")
        
        # 改进建议
        report.append(f"\n💡 改进建议:")
        if analysis['issue_types'].get('encoding_missing', 0) > 0:
            report.append("  • 为所有Python文件添加UTF-8编码声明")
        
        if analysis['issue_types'].get('import_order', 0) > 0:
            report.append("  • 按照PEP 8规范整理导入顺序")
        
        if analysis['issue_types'].get('module_docstring_missing', 0) > 0:
            report.append("  • 为模块添加文档字符串")
        
        if analysis['issue_types'].get('line_too_long', 0) > 0:
            report.append("  • 将过长的代码行拆分")
        
        if analysis['issue_types'].get('trailing_whitespace', 0) > 0:
            report.append("  • 清理行尾多余空格")
        
        return '\n'.join(report)


def main():
    """主函数"""
    analyzer = CodeStandardizationAnalyzer(project_root)
    report = analyzer.generate_report()
    print(report)
    
    # 保存报告
    report_file = project_root / 'tests' / 'code_standardization_report.txt'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n📄 报告已保存到: {report_file}")


if __name__ == "__main__":
    main()

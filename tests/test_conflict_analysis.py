# -*- coding: utf-8 -*-
"""
冲突分析工具：检查项目中的各种冲突
"""

import os
import ast
import re
from pathlib import Path
from collections import defaultdict, Counter
from typing import Set, Dict, List, Tuple, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent


class ConflictAnalyzer:
    """冲突分析器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.import_graph = defaultdict(set)  # 模块导入图
        self.function_names = defaultdict(list)  # 函数名 -> 文件列表
        self.class_names = defaultdict(list)  # 类名 -> 文件列表
        self.variable_names = defaultdict(list)  # 全局变量名 -> 文件列表
        self.file_names = defaultdict(list)  # 文件名 -> 路径列表
        self.signal_connections = defaultdict(list)  # 信号连接
        
    def analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """分析单个文件"""
        relative_path = file_path.relative_to(self.project_root)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析AST
            tree = ast.parse(content)
            
            # 分析导入
            imports = self._extract_imports(tree)
            self.import_graph[str(relative_path)] = imports
            
            # 分析定义
            definitions = self._extract_definitions(tree, str(relative_path))
            
            # 分析信号连接
            signals = self._extract_signal_connections(content, str(relative_path))
            
            # 记录文件名
            file_name = file_path.name
            self.file_names[file_name].append(str(relative_path))
            
            return {
                'imports': imports,
                'definitions': definitions,
                'signals': signals
            }
            
        except Exception as e:
            print(f"警告：无法分析文件 {file_path}: {e}")
            return {}
    
    def _extract_imports(self, tree: ast.AST) -> Set[str]:
        """提取导入信息"""
        imports = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
        
        return imports
    
    def _extract_definitions(self, tree: ast.AST, file_path: str) -> Dict[str, List[str]]:
        """提取函数、类、变量定义"""
        definitions = {'functions': [], 'classes': [], 'variables': []}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_name = node.name
                definitions['functions'].append(func_name)
                self.function_names[func_name].append(file_path)
            
            elif isinstance(node, ast.ClassDef):
                class_name = node.name
                definitions['classes'].append(class_name)
                self.class_names[class_name].append(file_path)
            
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        var_name = target.id
                        # 只记录全局变量（简单判断：大写或以_开头）
                        if var_name.isupper() or var_name.startswith('_'):
                            definitions['variables'].append(var_name)
                            self.variable_names[var_name].append(file_path)
        
        return definitions
    
    def _extract_signal_connections(self, content: str, file_path: str) -> List[str]:
        """提取信号连接"""
        signals = []
        
        # 查找 .connect( 模式
        connect_pattern = r'(\w+)\.connect\s*\('
        matches = re.findall(connect_pattern, content)
        
        for match in matches:
            signal_info = f"{match}.connect"
            signals.append(signal_info)
            self.signal_connections[signal_info].append(file_path)
        
        return signals
    
    def detect_circular_imports(self) -> List[List[str]]:
        """检测循环导入"""
        def dfs(node, path, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in self.import_graph.get(node, []):
                # 只检查项目内部模块
                if any(neighbor.startswith(prefix) for prefix in ['auto_approve', 'workers', 'capture', 'utils']):
                    neighbor_file = self._find_module_file(neighbor)
                    if neighbor_file:
                        if neighbor_file in rec_stack:
                            # 找到循环
                            cycle_start = path.index(neighbor_file)
                            return path[cycle_start:] + [neighbor_file]
                        
                        if neighbor_file not in visited:
                            cycle = dfs(neighbor_file, path + [neighbor_file], visited, rec_stack)
                            if cycle:
                                return cycle
            
            rec_stack.remove(node)
            return None
        
        cycles = []
        visited = set()
        
        for node in self.import_graph:
            if node not in visited:
                cycle = dfs(node, [node], visited, set())
                if cycle:
                    cycles.append(cycle)
        
        return cycles
    
    def _find_module_file(self, module_name: str) -> str:
        """根据模块名查找对应文件"""
        # 简单映射：模块名到文件路径
        parts = module_name.split('.')
        possible_paths = [
            f"{'/'.join(parts)}.py",
            f"{'/'.join(parts)}/__init__.py"
        ]
        
        for path in possible_paths:
            if path in self.import_graph:
                return path
        
        return None
    
    def detect_naming_conflicts(self) -> Dict[str, Dict[str, List[str]]]:
        """检测命名冲突"""
        conflicts = {
            'functions': {},
            'classes': {},
            'variables': {},
            'files': {}
        }
        
        # 函数名冲突
        for name, files in self.function_names.items():
            if len(files) > 1:
                conflicts['functions'][name] = files
        
        # 类名冲突
        for name, files in self.class_names.items():
            if len(files) > 1:
                conflicts['classes'][name] = files
        
        # 变量名冲突
        for name, files in self.variable_names.items():
            if len(files) > 1:
                conflicts['variables'][name] = files
        
        # 文件名冲突
        for name, paths in self.file_names.items():
            if len(paths) > 1:
                conflicts['files'][name] = paths
        
        return conflicts
    
    def detect_signal_conflicts(self) -> Dict[str, List[str]]:
        """检测信号连接冲突"""
        conflicts = {}
        
        for signal, files in self.signal_connections.items():
            if len(files) > 1:
                conflicts[signal] = files
        
        return conflicts
    
    def analyze_project(self) -> Dict[str, Any]:
        """分析整个项目"""
        python_files = list(self.project_root.rglob('*.py'))
        
        print(f"分析 {len(python_files)} 个Python文件...")
        
        for file_path in python_files:
            # 跳过虚拟环境和缓存
            if any(part in str(file_path) for part in ['.venv', '__pycache__', '.git']):
                continue
            
            self.analyze_file(file_path)
        
        # 检测各种冲突
        circular_imports = self.detect_circular_imports()
        naming_conflicts = self.detect_naming_conflicts()
        signal_conflicts = self.detect_signal_conflicts()
        
        return {
            'circular_imports': circular_imports,
            'naming_conflicts': naming_conflicts,
            'signal_conflicts': signal_conflicts,
            'import_graph_size': len(self.import_graph),
            'total_functions': len(self.function_names),
            'total_classes': len(self.class_names),
            'total_variables': len(self.variable_names)
        }
    
    def generate_report(self) -> str:
        """生成冲突分析报告"""
        analysis = self.analyze_project()
        
        report = []
        report.append("=" * 60)
        report.append("项目冲突分析报告")
        report.append("=" * 60)
        
        # 循环导入
        report.append(f"\n🔄 循环导入检查:")
        if analysis['circular_imports']:
            report.append(f"  ❌ 发现 {len(analysis['circular_imports'])} 个循环导入:")
            for i, cycle in enumerate(analysis['circular_imports'], 1):
                report.append(f"    {i}. {' -> '.join(cycle)}")
        else:
            report.append("  ✅ 未发现循环导入")
        
        # 命名冲突
        report.append(f"\n📛 命名冲突检查:")
        naming = analysis['naming_conflicts']
        
        if naming['functions']:
            report.append(f"  ⚠️  函数名冲突 ({len(naming['functions'])}):")
            for name, files in list(naming['functions'].items())[:5]:  # 只显示前5个
                report.append(f"    - {name}: {', '.join(files)}")
        
        if naming['classes']:
            report.append(f"  ⚠️  类名冲突 ({len(naming['classes'])}):")
            for name, files in list(naming['classes'].items())[:5]:
                report.append(f"    - {name}: {', '.join(files)}")
        
        if naming['files']:
            report.append(f"  ⚠️  文件名冲突 ({len(naming['files'])}):")
            for name, paths in naming['files'].items():
                report.append(f"    - {name}: {', '.join(paths)}")
        
        if not any(naming.values()):
            report.append("  ✅ 未发现严重命名冲突")
        
        # 信号冲突
        report.append(f"\n📡 信号连接检查:")
        if analysis['signal_conflicts']:
            report.append(f"  ⚠️  可能的信号冲突 ({len(analysis['signal_conflicts'])}):")
            for signal, files in list(analysis['signal_conflicts'].items())[:5]:
                report.append(f"    - {signal}: {', '.join(files)}")
        else:
            report.append("  ✅ 未发现明显信号冲突")
        
        # 统计信息
        report.append(f"\n📊 项目统计:")
        report.append(f"  - 模块数: {analysis['import_graph_size']}")
        report.append(f"  - 函数数: {analysis['total_functions']}")
        report.append(f"  - 类数: {analysis['total_classes']}")
        report.append(f"  - 全局变量数: {analysis['total_variables']}")
        
        return '\n'.join(report)


def main():
    """主函数"""
    analyzer = ConflictAnalyzer(project_root)
    report = analyzer.generate_report()
    print(report)
    
    # 保存报告
    report_file = project_root / 'tests' / 'conflict_analysis_report.txt'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n📄 报告已保存到: {report_file}")


if __name__ == "__main__":
    main()

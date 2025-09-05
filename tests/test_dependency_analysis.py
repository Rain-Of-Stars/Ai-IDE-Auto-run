# -*- coding: utf-8 -*-
"""
依赖分析工具：检查项目中实际使用的依赖包
"""

import os
import sys
import ast
import re
from pathlib import Path
from collections import defaultdict, Counter
from typing import Set, Dict, List, Tuple

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class DependencyAnalyzer:
    """依赖分析器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.imports_found = defaultdict(set)  # 文件 -> 导入集合
        self.third_party_imports = Counter()  # 第三方库计数
        self.standard_library_imports = Counter()  # 标准库计数
        self.local_imports = Counter()  # 本地模块计数
        
        # Python标准库模块（部分常用的）
        self.standard_modules = {
            'os', 'sys', 'time', 'datetime', 'json', 'pickle', 'logging',
            'threading', 'multiprocessing', 'queue', 'collections', 'typing',
            'pathlib', 'shutil', 'subprocess', 'signal', 'warnings', 'ctypes',
            'ast', 're', 'uuid', 'traceback', 'hashlib', 'dataclasses',
            'functools', 'itertools', 'operator', 'math', 'random', 'string',
            'io', 'tempfile', 'glob', 'fnmatch', 'csv', 'configparser',
            'urllib', 'http', 'email', 'base64', 'zlib', 'gzip', 'tarfile',
            'zipfile', 'sqlite3', 'xml', 'html', 'unittest', 'doctest'
        }
        
        # 已知第三方库映射（包名 -> requirements中的名称）
        self.package_mapping = {
            'cv2': 'opencv-python',
            'numpy': 'numpy', 
            'np': 'numpy',
            'PIL': 'Pillow',
            'PySide6': 'PySide6',
            'psutil': 'psutil',
            'requests': 'requests',
            'aiohttp': 'aiohttp',
            'websockets': 'websockets',
            'qasync': 'qasync',
            'windows_capture': 'windows-capture'
        }
    
    def analyze_file(self, file_path: Path) -> Set[str]:
        """分析单个Python文件的导入"""
        imports = set()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 使用AST解析
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.add(alias.name.split('.')[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.add(node.module.split('.')[0])
            except SyntaxError:
                # AST解析失败，使用正则表达式
                import_patterns = [
                    r'^\s*import\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                    r'^\s*from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import'
                ]
                
                for line in content.split('\n'):
                    for pattern in import_patterns:
                        match = re.match(pattern, line)
                        if match:
                            imports.add(match.group(1))
        
        except Exception as e:
            print(f"警告：无法分析文件 {file_path}: {e}")
        
        return imports
    
    def categorize_import(self, import_name: str) -> str:
        """分类导入：standard/third_party/local"""
        if import_name in self.standard_modules:
            return 'standard'
        elif import_name in self.package_mapping or import_name in ['cv2', 'numpy', 'PIL', 'PySide6', 'psutil', 'requests', 'aiohttp', 'websockets', 'qasync']:
            return 'third_party'
        elif import_name in ['auto_approve', 'workers', 'capture', 'utils', 'tests', 'tools']:
            return 'local'
        else:
            # 尝试判断是否为第三方库
            if import_name.islower() and '_' not in import_name and len(import_name) > 2:
                return 'third_party'
            return 'local'
    
    def analyze_project(self) -> Dict:
        """分析整个项目"""
        python_files = list(self.project_root.rglob('*.py'))
        
        print(f"分析 {len(python_files)} 个Python文件...")
        
        for file_path in python_files:
            # 跳过虚拟环境和缓存
            if any(part in str(file_path) for part in ['.venv', '__pycache__', '.git']):
                continue
            
            imports = self.analyze_file(file_path)
            relative_path = file_path.relative_to(self.project_root)
            self.imports_found[str(relative_path)] = imports
            
            # 分类统计
            for imp in imports:
                category = self.categorize_import(imp)
                if category == 'standard':
                    self.standard_library_imports[imp] += 1
                elif category == 'third_party':
                    self.third_party_imports[imp] += 1
                else:
                    self.local_imports[imp] += 1
        
        return {
            'files_analyzed': len(python_files),
            'total_imports': sum(len(imports) for imports in self.imports_found.values()),
            'third_party': dict(self.third_party_imports),
            'standard': dict(self.standard_library_imports),
            'local': dict(self.local_imports)
        }
    
    def check_requirements_consistency(self) -> Dict:
        """检查requirements.txt与实际使用的一致性"""
        requirements_file = self.project_root / 'requirements.txt'
        
        if not requirements_file.exists():
            return {'error': 'requirements.txt 不存在'}
        
        # 读取requirements.txt
        declared_packages = set()
        with open(requirements_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # 提取包名（去掉版本号）
                    package = re.split(r'[>=<!=]', line)[0].strip()
                    declared_packages.add(package)
        
        # 映射实际使用的包到requirements名称
        used_packages = set()
        for imp in self.third_party_imports:
            if imp in self.package_mapping:
                used_packages.add(self.package_mapping[imp])
            else:
                used_packages.add(imp)
        
        # 分析差异
        unused_declared = declared_packages - used_packages
        undeclared_used = used_packages - declared_packages
        
        return {
            'declared_packages': sorted(declared_packages),
            'used_packages': sorted(used_packages),
            'unused_declared': sorted(unused_declared),
            'undeclared_used': sorted(undeclared_used),
            'consistent': len(unused_declared) == 0 and len(undeclared_used) == 0
        }
    
    def generate_report(self) -> str:
        """生成分析报告"""
        analysis = self.analyze_project()
        consistency = self.check_requirements_consistency()
        
        report = []
        report.append("=" * 60)
        report.append("项目依赖分析报告")
        report.append("=" * 60)
        
        report.append(f"\n📊 统计信息:")
        report.append(f"  - 分析文件数: {analysis['files_analyzed']}")
        report.append(f"  - 总导入数: {analysis['total_imports']}")
        report.append(f"  - 第三方库: {len(analysis['third_party'])}")
        report.append(f"  - 标准库: {len(analysis['standard'])}")
        report.append(f"  - 本地模块: {len(analysis['local'])}")
        
        report.append(f"\n📦 第三方库使用情况:")
        for package, count in sorted(analysis['third_party'].items(), key=lambda x: x[1], reverse=True):
            report.append(f"  - {package}: {count} 次")
        
        report.append(f"\n🔧 requirements.txt 一致性检查:")
        if 'error' in consistency:
            report.append(f"  ❌ {consistency['error']}")
        else:
            if consistency['consistent']:
                report.append("  ✅ requirements.txt 与实际使用一致")
            else:
                if consistency['unused_declared']:
                    report.append("  ⚠️  声明但未使用的包:")
                    for pkg in consistency['unused_declared']:
                        report.append(f"    - {pkg}")
                
                if consistency['undeclared_used']:
                    report.append("  ❌ 使用但未声明的包:")
                    for pkg in consistency['undeclared_used']:
                        report.append(f"    - {pkg}")
        
        report.append(f"\n🏗️  常用标准库:")
        top_standard = sorted(analysis['standard'].items(), key=lambda x: x[1], reverse=True)[:10]
        for lib, count in top_standard:
            report.append(f"  - {lib}: {count} 次")
        
        return '\n'.join(report)


def main():
    """主函数"""
    print("开始依赖分析...")
    print(f"项目根目录: {project_root}")

    analyzer = DependencyAnalyzer(project_root)
    print("生成分析报告...")
    report = analyzer.generate_report()
    print(report)

    # 保存报告
    report_file = project_root / 'tests' / 'dependency_analysis_report.txt'
    print(f"保存报告到: {report_file}")
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✅ 报告已保存到: {report_file}")
    except Exception as e:
        print(f"❌ 保存报告失败: {e}")


if __name__ == "__main__":
    main()

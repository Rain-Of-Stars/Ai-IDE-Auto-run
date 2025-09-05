# -*- coding: utf-8 -*-
"""
代码冗余分析工具：检查项目中的重复代码和冗余导入
"""

import os
import ast
import re
import hashlib
from pathlib import Path
from collections import defaultdict, Counter
from typing import Set, Dict, List, Tuple, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent


class RedundancyAnalyzer:
    """代码冗余分析器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.function_signatures = defaultdict(list)  # 函数签名 -> 文件列表
        self.code_blocks = defaultdict(list)  # 代码块哈希 -> 文件列表
        self.import_usage = defaultdict(set)  # 文件 -> 使用的导入
        self.all_imports = defaultdict(set)  # 文件 -> 所有导入
        self.unused_imports = defaultdict(set)  # 文件 -> 未使用的导入
        
    def analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """分析单个文件"""
        relative_path = file_path.relative_to(self.project_root)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析AST
            tree = ast.parse(content)
            
            # 分析函数
            functions = self._extract_functions(tree, str(relative_path))
            
            # 分析代码块
            code_blocks = self._extract_code_blocks(content, str(relative_path))
            
            # 分析导入使用
            imports, used_imports = self._analyze_imports(tree, content, str(relative_path))
            
            return {
                'functions': functions,
                'code_blocks': code_blocks,
                'imports': imports,
                'used_imports': used_imports
            }
            
        except Exception as e:
            print(f"警告：无法分析文件 {file_path}: {e}")
            return {}
    
    def _extract_functions(self, tree: ast.AST, file_path: str) -> List[Dict[str, Any]]:
        """提取函数信息"""
        functions = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 生成函数签名
                args = [arg.arg for arg in node.args.args]
                signature = f"{node.name}({', '.join(args)})"
                
                # 计算函数体哈希
                func_lines = []
                if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                    # 这里简化处理，实际应该提取函数体代码
                    body_hash = hashlib.md5(signature.encode()).hexdigest()[:8]
                else:
                    body_hash = hashlib.md5(signature.encode()).hexdigest()[:8]
                
                func_info = {
                    'name': node.name,
                    'signature': signature,
                    'body_hash': body_hash,
                    'line_start': getattr(node, 'lineno', 0),
                    'line_end': getattr(node, 'end_lineno', 0)
                }
                
                functions.append(func_info)
                self.function_signatures[signature].append(file_path)
        
        return functions
    
    def _extract_code_blocks(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """提取代码块（用于检测重复代码）"""
        lines = content.split('\n')
        blocks = []
        
        # 检查连续的非空行组成的代码块（至少3行）
        current_block = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                current_block.append((i + 1, stripped))
            else:
                if len(current_block) >= 3:
                    # 生成代码块哈希
                    block_content = '\n'.join([line for _, line in current_block])
                    block_hash = hashlib.md5(block_content.encode()).hexdigest()[:8]
                    
                    block_info = {
                        'hash': block_hash,
                        'start_line': current_block[0][0],
                        'end_line': current_block[-1][0],
                        'line_count': len(current_block),
                        'content_preview': block_content[:100] + '...' if len(block_content) > 100 else block_content
                    }
                    
                    blocks.append(block_info)
                    self.code_blocks[block_hash].append((file_path, block_info))
                
                current_block = []
        
        return blocks
    
    def _analyze_imports(self, tree: ast.AST, content: str, file_path: str) -> Tuple[Set[str], Set[str]]:
        """分析导入和使用情况"""
        imports = set()
        used_imports = set()
        
        # 提取所有导入
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    imports.add(module_name)
                    
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    imports.add(module_name)
                    
                    # 记录具体导入的名称
                    for alias in node.names:
                        imports.add(alias.name)
        
        # 检查导入使用（简单的文本搜索）
        for imp in imports:
            # 检查是否在代码中使用
            if re.search(rf'\b{re.escape(imp)}\b', content):
                used_imports.add(imp)
        
        self.all_imports[file_path] = imports
        self.import_usage[file_path] = used_imports
        self.unused_imports[file_path] = imports - used_imports
        
        return imports, used_imports
    
    def detect_duplicate_functions(self) -> Dict[str, List[str]]:
        """检测重复函数"""
        duplicates = {}
        
        for signature, files in self.function_signatures.items():
            if len(files) > 1:
                duplicates[signature] = files
        
        return duplicates
    
    def detect_duplicate_code_blocks(self) -> Dict[str, List[Tuple[str, Dict]]]:
        """检测重复代码块"""
        duplicates = {}
        
        for block_hash, occurrences in self.code_blocks.items():
            if len(occurrences) > 1:
                duplicates[block_hash] = occurrences
        
        return duplicates
    
    def detect_unused_imports(self) -> Dict[str, Set[str]]:
        """检测未使用的导入"""
        return dict(self.unused_imports)
    
    def analyze_import_patterns(self) -> Dict[str, Any]:
        """分析导入模式"""
        all_imports_count = Counter()
        used_imports_count = Counter()
        
        for file_path, imports in self.all_imports.items():
            for imp in imports:
                all_imports_count[imp] += 1
        
        for file_path, used_imports in self.import_usage.items():
            for imp in used_imports:
                used_imports_count[imp] += 1
        
        # 计算使用率
        import_usage_rate = {}
        for imp, total_count in all_imports_count.items():
            used_count = used_imports_count.get(imp, 0)
            usage_rate = used_count / total_count if total_count > 0 else 0
            import_usage_rate[imp] = {
                'total_imports': total_count,
                'used_imports': used_count,
                'usage_rate': usage_rate
            }
        
        return import_usage_rate
    
    def analyze_project(self) -> Dict[str, Any]:
        """分析整个项目"""
        python_files = list(self.project_root.rglob('*.py'))
        
        print(f"分析 {len(python_files)} 个Python文件...")
        
        for file_path in python_files:
            # 跳过虚拟环境和缓存
            if any(part in str(file_path) for part in ['.venv', '__pycache__', '.git']):
                continue
            
            self.analyze_file(file_path)
        
        # 检测各种冗余
        duplicate_functions = self.detect_duplicate_functions()
        duplicate_code_blocks = self.detect_duplicate_code_blocks()
        unused_imports = self.detect_unused_imports()
        import_patterns = self.analyze_import_patterns()
        
        return {
            'duplicate_functions': duplicate_functions,
            'duplicate_code_blocks': duplicate_code_blocks,
            'unused_imports': unused_imports,
            'import_patterns': import_patterns,
            'total_files': len(python_files),
            'total_functions': len(self.function_signatures),
            'total_code_blocks': len(self.code_blocks)
        }
    
    def generate_report(self) -> str:
        """生成冗余分析报告"""
        analysis = self.analyze_project()
        
        report = []
        report.append("=" * 60)
        report.append("代码冗余分析报告")
        report.append("=" * 60)
        
        # 重复函数
        report.append(f"\n🔄 重复函数检查:")
        if analysis['duplicate_functions']:
            report.append(f"  ❌ 发现 {len(analysis['duplicate_functions'])} 个重复函数:")
            for signature, files in list(analysis['duplicate_functions'].items())[:5]:
                report.append(f"    - {signature}")
                for file in files:
                    report.append(f"      • {file}")
        else:
            report.append("  ✅ 未发现重复函数")
        
        # 重复代码块
        report.append(f"\n📋 重复代码块检查:")
        if analysis['duplicate_code_blocks']:
            report.append(f"  ❌ 发现 {len(analysis['duplicate_code_blocks'])} 个重复代码块:")
            for block_hash, occurrences in list(analysis['duplicate_code_blocks'].items())[:3]:
                report.append(f"    - 代码块 {block_hash} ({len(occurrences)} 处重复):")
                for file_path, block_info in occurrences:
                    report.append(f"      • {file_path} (行 {block_info['start_line']}-{block_info['end_line']})")
        else:
            report.append("  ✅ 未发现明显重复代码块")
        
        # 未使用的导入
        report.append(f"\n📦 未使用导入检查:")
        total_unused = sum(len(unused) for unused in analysis['unused_imports'].values())
        if total_unused > 0:
            report.append(f"  ⚠️  发现 {total_unused} 个未使用的导入:")
            count = 0
            for file_path, unused in analysis['unused_imports'].items():
                if unused and count < 5:  # 只显示前5个文件
                    report.append(f"    - {file_path}: {', '.join(list(unused)[:3])}")
                    count += 1
        else:
            report.append("  ✅ 未发现明显未使用的导入")
        
        # 导入模式分析
        report.append(f"\n📊 导入使用率分析:")
        low_usage_imports = []
        for imp, stats in analysis['import_patterns'].items():
            if stats['usage_rate'] < 0.5 and stats['total_imports'] > 2:
                low_usage_imports.append((imp, stats))
        
        if low_usage_imports:
            report.append(f"  ⚠️  低使用率导入 (使用率 < 50%):")
            for imp, stats in sorted(low_usage_imports, key=lambda x: x[1]['usage_rate'])[:5]:
                report.append(f"    - {imp}: {stats['used_imports']}/{stats['total_imports']} ({stats['usage_rate']:.1%})")
        else:
            report.append("  ✅ 导入使用率良好")
        
        # 统计信息
        report.append(f"\n📊 项目统计:")
        report.append(f"  - 分析文件数: {analysis['total_files']}")
        report.append(f"  - 函数总数: {analysis['total_functions']}")
        report.append(f"  - 代码块总数: {analysis['total_code_blocks']}")
        report.append(f"  - 重复函数: {len(analysis['duplicate_functions'])}")
        report.append(f"  - 重复代码块: {len(analysis['duplicate_code_blocks'])}")
        
        return '\n'.join(report)


def main():
    """主函数"""
    analyzer = RedundancyAnalyzer(project_root)
    report = analyzer.generate_report()
    print(report)
    
    # 保存报告
    report_file = project_root / 'tests' / 'redundancy_analysis_report.txt'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n📄 报告已保存到: {report_file}")


if __name__ == "__main__":
    main()

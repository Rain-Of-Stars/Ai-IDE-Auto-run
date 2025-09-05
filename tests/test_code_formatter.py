# -*- coding: utf-8 -*-
"""
代码格式化工具：自动修复常见的代码规范问题
"""

import os
import re
import ast
from pathlib import Path
from typing import List, Dict, Any, Tuple

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent


class CodeFormatter:
    """代码格式化器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.fixes_applied = []
        self.backup_dir = project_root / 'backups'
        
        # 确保备份目录存在
        self.backup_dir.mkdir(exist_ok=True)
    
    def format_file(self, file_path: Path, create_backup: bool = True) -> Dict[str, Any]:
        """格式化单个文件
        
        Args:
            file_path: 文件路径
            create_backup: 是否创建备份
        
        Returns:
            格式化结果
        """
        relative_path = file_path.relative_to(self.project_root)
        
        try:
            # 读取原文件
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # 创建备份
            if create_backup:
                backup_path = self.backup_dir / f"{relative_path.name}.backup"
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
            
            # 应用格式化
            formatted_content = original_content
            fixes = []
            
            # 1. 添加编码声明
            formatted_content, encoding_fix = self._add_encoding_declaration(formatted_content)
            if encoding_fix:
                fixes.append(encoding_fix)
            
            # 2. 清理尾随空格
            formatted_content, whitespace_fixes = self._remove_trailing_whitespace(formatted_content)
            fixes.extend(whitespace_fixes)
            
            # 3. 修复注释间距
            formatted_content, comment_fixes = self._fix_comment_spacing(formatted_content)
            fixes.extend(comment_fixes)
            
            # 4. 整理导入顺序
            formatted_content, import_fixes = self._organize_imports(formatted_content)
            fixes.extend(import_fixes)
            
            # 5. 添加基础文档字符串
            formatted_content, docstring_fixes = self._add_basic_docstrings(formatted_content, str(relative_path))
            fixes.extend(docstring_fixes)
            
            # 写入格式化后的内容
            if formatted_content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(formatted_content)
            
            return {
                'file_path': str(relative_path),
                'fixes_applied': fixes,
                'fix_count': len(fixes),
                'success': True
            }
            
        except Exception as e:
            return {
                'file_path': str(relative_path),
                'fixes_applied': [],
                'fix_count': 0,
                'success': False,
                'error': str(e)
            }
    
    def _add_encoding_declaration(self, content: str) -> Tuple[str, Dict[str, Any]]:
        """添加编码声明"""
        lines = content.split('\n')
        
        # 检查前两行是否已有编码声明
        encoding_patterns = [
            r'# -\*- coding: utf-8 -\*-',
            r'# coding: utf-8',
            r'# coding=utf-8'
        ]
        
        has_encoding = False
        for line in lines[:2]:
            for pattern in encoding_patterns:
                if re.search(pattern, line):
                    has_encoding = True
                    break
            if has_encoding:
                break
        
        if not has_encoding:
            # 添加编码声明
            encoding_line = '# -*- coding: utf-8 -*-'
            
            # 如果第一行是shebang，在第二行添加
            if lines and lines[0].startswith('#!'):
                lines.insert(1, encoding_line)
            else:
                lines.insert(0, encoding_line)
            
            return '\n'.join(lines), {
                'type': 'encoding_added',
                'description': '添加UTF-8编码声明'
            }
        
        return content, None
    
    def _remove_trailing_whitespace(self, content: str) -> Tuple[str, List[Dict[str, Any]]]:
        """移除尾随空格"""
        lines = content.split('\n')
        fixes = []
        
        for i, line in enumerate(lines):
            if line.rstrip() != line and line.strip():
                lines[i] = line.rstrip()
                fixes.append({
                    'type': 'trailing_whitespace_removed',
                    'description': f'移除第{i+1}行尾随空格',
                    'line': i + 1
                })
        
        return '\n'.join(lines), fixes
    
    def _fix_comment_spacing(self, content: str) -> Tuple[str, List[Dict[str, Any]]]:
        """修复注释间距"""
        lines = content.split('\n')
        fixes = []
        
        for i, line in enumerate(lines):
            # 检查行内注释间距
            if '#' in line and not line.strip().startswith('#'):
                # 查找注释位置
                comment_pos = line.index('#')
                before_comment = line[:comment_pos]
                comment_part = line[comment_pos:]
                
                # 检查注释前是否有足够空格
                if before_comment and not before_comment.endswith('  '):
                    # 确保注释前有两个空格
                    before_comment = before_comment.rstrip() + '  '
                    lines[i] = before_comment + comment_part
                    fixes.append({
                        'type': 'comment_spacing_fixed',
                        'description': f'修复第{i+1}行注释间距',
                        'line': i + 1
                    })
        
        return '\n'.join(lines), fixes
    
    def _organize_imports(self, content: str) -> Tuple[str, List[Dict[str, Any]]]:
        """整理导入顺序（简化版）"""
        try:
            tree = ast.parse(content)
            lines = content.split('\n')
            
            # 查找导入语句的行号
            import_lines = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    import_lines.append(node.lineno - 1)  # AST行号从1开始
            
            if not import_lines:
                return content, []
            
            # 提取导入语句
            imports = []
            for line_no in sorted(import_lines):
                if line_no < len(lines):
                    imports.append((line_no, lines[line_no]))
            
            # 简单的导入分类和排序
            standard_imports = []
            third_party_imports = []
            local_imports = []
            
            standard_modules = {
                'os', 'sys', 'time', 'datetime', 'json', 'pickle', 'logging',
                'threading', 'multiprocessing', 'queue', 'collections', 'typing',
                'pathlib', 'shutil', 'subprocess', 'signal', 'warnings', 'ctypes'
            }
            
            for line_no, import_line in imports:
                # 简单分类
                if any(mod in import_line for mod in standard_modules):
                    standard_imports.append(import_line)
                elif any(mod in import_line for mod in ['PySide6', 'cv2', 'numpy', 'PIL']):
                    third_party_imports.append(import_line)
                else:
                    local_imports.append(import_line)
            
            # 重新组织导入
            organized_imports = []
            if standard_imports:
                organized_imports.extend(sorted(standard_imports))
                organized_imports.append('')  # 空行分隔
            
            if third_party_imports:
                organized_imports.extend(sorted(third_party_imports))
                organized_imports.append('')  # 空行分隔
            
            if local_imports:
                organized_imports.extend(sorted(local_imports))
                organized_imports.append('')  # 空行分隔
            
            # 替换原有导入
            if organized_imports:
                # 移除最后的空行
                if organized_imports and organized_imports[-1] == '':
                    organized_imports.pop()
                
                # 找到导入区域的开始和结束
                first_import = min(import_lines)
                last_import = max(import_lines)
                
                # 替换导入区域
                new_lines = (lines[:first_import] + 
                           organized_imports + 
                           lines[last_import + 1:])
                
                new_content = '\n'.join(new_lines)
                
                if new_content != content:
                    return new_content, [{
                        'type': 'imports_organized',
                        'description': '整理导入顺序'
                    }]
        
        except SyntaxError:
            pass  # 语法错误时跳过导入整理
        
        return content, []
    
    def _add_basic_docstrings(self, content: str, file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
        """添加基础文档字符串"""
        try:
            tree = ast.parse(content)
            lines = content.split('\n')
            fixes = []
            
            # 检查模块文档字符串
            if not ast.get_docstring(tree):
                # 生成基础模块文档字符串
                module_name = Path(file_path).stem
                docstring = f'"""\n{module_name} 模块\n\n模块功能描述\n"""'
                
                # 找到合适的插入位置（编码声明之后）
                insert_pos = 0
                for i, line in enumerate(lines):
                    if line.strip().startswith('#') and ('coding' in line or 'encoding' in line):
                        insert_pos = i + 1
                        break
                
                lines.insert(insert_pos, docstring)
                fixes.append({
                    'type': 'module_docstring_added',
                    'description': '添加模块文档字符串'
                })
            
            if fixes:
                return '\n'.join(lines), fixes
        
        except SyntaxError:
            pass
        
        return content, []
    
    def format_project(self, file_pattern: str = "*.py", 
                      exclude_patterns: List[str] = None) -> Dict[str, Any]:
        """格式化整个项目
        
        Args:
            file_pattern: 文件匹配模式
            exclude_patterns: 排除模式列表
        
        Returns:
            格式化结果
        """
        if exclude_patterns is None:
            exclude_patterns = ['.venv', '__pycache__', '.git', 'backups']
        
        python_files = list(self.project_root.rglob(file_pattern))
        
        # 过滤排除的文件
        filtered_files = []
        for file_path in python_files:
            if not any(pattern in str(file_path) for pattern in exclude_patterns):
                filtered_files.append(file_path)
        
        print(f"格式化 {len(filtered_files)} 个Python文件...")
        
        results = []
        total_fixes = 0
        
        for file_path in filtered_files:
            result = self.format_file(file_path)
            results.append(result)
            total_fixes += result['fix_count']
            
            if result['success'] and result['fix_count'] > 0:
                print(f"✅ {result['file_path']}: {result['fix_count']} 个修复")
            elif not result['success']:
                print(f"❌ {result['file_path']}: {result.get('error', '未知错误')}")
        
        return {
            'total_files': len(filtered_files),
            'total_fixes': total_fixes,
            'successful_files': sum(1 for r in results if r['success']),
            'failed_files': sum(1 for r in results if not r['success']),
            'results': results
        }
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """生成格式化报告"""
        report = []
        report.append("=" * 60)
        report.append("代码格式化报告")
        report.append("=" * 60)
        
        report.append(f"\n📊 格式化统计:")
        report.append(f"  - 处理文件数: {results['total_files']}")
        report.append(f"  - 成功文件数: {results['successful_files']}")
        report.append(f"  - 失败文件数: {results['failed_files']}")
        report.append(f"  - 总修复数: {results['total_fixes']}")
        
        # 修复类型统计
        fix_types = {}
        for result in results['results']:
            for fix in result['fixes_applied']:
                fix_type = fix['type']
                fix_types[fix_type] = fix_types.get(fix_type, 0) + 1
        
        if fix_types:
            report.append(f"\n🔧 修复类型统计:")
            for fix_type, count in sorted(fix_types.items(), key=lambda x: x[1], reverse=True):
                report.append(f"  - {fix_type}: {count}")
        
        # 修复最多的文件
        report.append(f"\n📁 修复最多的文件:")
        file_fixes = [(r['file_path'], r['fix_count']) for r in results['results'] if r['fix_count'] > 0]
        file_fixes.sort(key=lambda x: x[1], reverse=True)
        
        for file_path, fix_count in file_fixes[:5]:
            report.append(f"  - {file_path}: {fix_count} 个修复")
        
        return '\n'.join(report)


def main():
    """主函数"""
    formatter = CodeFormatter(project_root)
    
    # 格式化项目
    results = formatter.format_project()
    
    # 生成报告
    report = formatter.generate_report(results)
    print(report)
    
    # 保存报告
    report_file = project_root / 'tests' / 'code_formatting_report.txt'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n📄 报告已保存到: {report_file}")


if __name__ == "__main__":
    main()

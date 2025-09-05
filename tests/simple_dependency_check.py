# -*- coding: utf-8 -*-
"""
简单依赖检查工具
"""

import os
import re
from pathlib import Path

def analyze_imports():
    """分析项目导入"""
    project_root = Path(__file__).parent.parent
    
    # 收集所有Python文件
    python_files = []
    for root, dirs, files in os.walk(project_root):
        # 跳过虚拟环境和缓存
        dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__', '.git']]
        for file in files:
            if file.endswith('.py'):
                python_files.append(Path(root) / file)
    
    print(f"找到 {len(python_files)} 个Python文件")
    
    # 分析导入
    third_party_imports = set()
    standard_imports = set()
    local_imports = set()
    
    # 已知第三方库
    known_third_party = {
        'PySide6', 'cv2', 'numpy', 'PIL', 'psutil', 'requests', 
        'aiohttp', 'websockets', 'qasync', 'windows_capture'
    }
    
    # Python标准库（部分）
    known_standard = {
        'os', 'sys', 'time', 'datetime', 'json', 'pickle', 'logging',
        'threading', 'multiprocessing', 'queue', 'collections', 'typing',
        'pathlib', 'shutil', 'subprocess', 'signal', 'warnings', 'ctypes',
        'ast', 're', 'uuid', 'traceback', 'hashlib', 'dataclasses',
        'functools', 'itertools', 'operator', 'math', 'random', 'string'
    }
    
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 使用正则表达式查找导入
            import_patterns = [
                r'^\s*import\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                r'^\s*from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import'
            ]
            
            for line in content.split('\n'):
                for pattern in import_patterns:
                    match = re.match(pattern, line.strip())
                    if match:
                        module = match.group(1)
                        
                        if module in known_third_party:
                            third_party_imports.add(module)
                        elif module in known_standard:
                            standard_imports.add(module)
                        elif module in ['auto_approve', 'workers', 'capture', 'utils', 'tests', 'tools']:
                            local_imports.add(module)
                        else:
                            # 其他可能的第三方库
                            if module.islower() and len(module) > 2:
                                third_party_imports.add(module)
                            else:
                                local_imports.add(module)
        
        except Exception as e:
            print(f"警告：无法分析 {file_path}: {e}")
    
    print("\n=== 依赖分析结果 ===")
    print(f"\n第三方库 ({len(third_party_imports)}):")
    for imp in sorted(third_party_imports):
        print(f"  - {imp}")
    
    print(f"\n标准库 ({len(standard_imports)}):")
    for imp in sorted(standard_imports):
        print(f"  - {imp}")
    
    print(f"\n本地模块 ({len(local_imports)}):")
    for imp in sorted(local_imports):
        print(f"  - {imp}")
    
    # 检查requirements.txt
    requirements_file = project_root / 'requirements.txt'
    if requirements_file.exists():
        print(f"\n=== requirements.txt 检查 ===")
        with open(requirements_file, 'r', encoding='utf-8') as f:
            declared = set()
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    package = re.split(r'[>=<!=]', line)[0].strip()
                    declared.add(package)
        
        print(f"声明的包 ({len(declared)}):")
        for pkg in sorted(declared):
            print(f"  - {pkg}")
        
        # 映射检查
        package_mapping = {
            'cv2': 'opencv-python',
            'PIL': 'Pillow',
            'windows_capture': 'windows-capture'
        }
        
        used_packages = set()
        for imp in third_party_imports:
            if imp in package_mapping:
                used_packages.add(package_mapping[imp])
            else:
                used_packages.add(imp)
        
        unused = declared - used_packages
        missing = used_packages - declared
        
        if unused:
            print(f"\n⚠️  可能未使用的包:")
            for pkg in sorted(unused):
                print(f"  - {pkg}")
        
        if missing:
            print(f"\n❌ 缺失的包:")
            for pkg in sorted(missing):
                print(f"  - {pkg}")
        
        if not unused and not missing:
            print("\n✅ requirements.txt 与实际使用基本一致")

if __name__ == "__main__":
    analyze_imports()

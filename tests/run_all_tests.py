#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试运行器

运行tests文件夹中的所有测试文件。
使用方法：
    python run_all_tests.py
"""

import os
import sys
import subprocess
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(str(project_root))  # 切换到项目根目录

def run_test_file(test_file: str) -> bool:
    """运行单个测试文件"""
    print(f"\n{'='*60}")
    print(f"运行测试: {test_file}")
    print(f"{'='*60}")
    
    try:
        # 设置环境变量以支持UTF-8
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        # 使用subprocess运行测试文件
        result = subprocess.run(
            [sys.executable, test_file],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',  # 处理编码错误
            env=env
        )
        
        # 输出结果
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("错误输出:", result.stderr)
            
        success = result.returncode == 0
        status = "✅ 通过" if success else "❌ 失败"
        print(f"\n测试结果: {status}")
        
        return success
        
    except Exception as e:
        print(f"❌ 运行测试时发生异常: {e}")
        return False

def main():
    """主函数"""
    print("开始运行所有测试...")
    
    # 获取tests目录中的所有测试文件
    tests_dir = Path(__file__).parent
    test_files = []
    
    for file in tests_dir.glob("test_*.py"):
        if file.name != "run_all_tests.py":
            test_files.append(str(file))
    
    # 添加demo文件
    for file in tests_dir.glob("demo_*.py"):
        test_files.append(str(file))
    
    if not test_files:
        print("未找到测试文件")
        return 1
    
    print(f"找到 {len(test_files)} 个测试文件:")
    for test_file in test_files:
        print(f"  - {os.path.basename(test_file)}")
    
    # 运行所有测试
    results = []
    for test_file in test_files:
        success = run_test_file(test_file)
        results.append((os.path.basename(test_file), success))
    
    # 输出总结
    print(f"\n{'='*60}")
    print("测试总结")
    print(f"{'='*60}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{test_name:<40} {status}")
    
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("[SUCCESS] 所有测试都通过了！")
        return 0
    else:
        print(f"[WARNING] 有 {total - passed} 个测试失败")
        return 1

if __name__ == "__main__":
    exit(main())
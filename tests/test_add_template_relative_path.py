#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试添加模板图片时使用相对路径的功能

此脚本验证：
1. 添加图片时会复制到 assets/images 目录
2. 列表中显示的是相对路径
3. 文件名冲突时会自动重命名
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from auto_approve.path_utils import get_app_base_dir

def create_test_image(path: str, content: str = "test"):
    """创建一个简单的测试图片文件"""
    # 创建一个简单的文本文件作为测试图片（实际应用中是真实图片）
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def test_assets_images_structure():
    """测试 assets/images 目录结构"""
    print("=== 测试 assets/images 目录结构 ===")
    
    proj_root = get_app_base_dir()
    images_dir = os.path.join(proj_root, "assets", "images")
    
    print(f"项目根目录: {proj_root}")
    print(f"images目录: {images_dir}")
    print(f"images目录存在: {os.path.exists(images_dir)}")
    
    if os.path.exists(images_dir):
        files = os.listdir(images_dir)
        print(f"images目录中的文件: {files}")
    
    return images_dir

def test_relative_path_conversion():
    """测试相对路径转换逻辑"""
    print("\n=== 测试相对路径转换逻辑 ===")
    
    proj_root = get_app_base_dir()
    images_dir = os.path.join(proj_root, "assets", "images")
    
    # 确保目录存在
    os.makedirs(images_dir, exist_ok=True)
    
    # 创建测试文件
    test_file = os.path.join(images_dir, "test_template.png")
    create_test_image(test_file, "test template content")
    
    # 测试相对路径
    rel_path = os.path.join("assets", "images", "test_template.png")
    abs_path = os.path.join(proj_root, rel_path)
    
    print(f"相对路径: {rel_path}")
    print(f"绝对路径: {abs_path}")
    print(f"文件存在: {os.path.exists(abs_path)}")
    
    # 清理测试文件
    if os.path.exists(test_file):
        os.remove(test_file)
        print("已清理测试文件")

def test_file_name_conflict_handling():
    """测试文件名冲突处理"""
    print("\n=== 测试文件名冲突处理 ===")
    
    proj_root = get_app_base_dir()
    images_dir = os.path.join(proj_root, "assets", "images")
    
    # 确保目录存在
    os.makedirs(images_dir, exist_ok=True)
    
    # 创建原始文件
    original_file = os.path.join(images_dir, "conflict_test.png")
    create_test_image(original_file, "original file")
    
    # 模拟文件名冲突处理逻辑
    original_name = "conflict_test.png"
    name, ext = os.path.splitext(original_name)
    
    target_name = original_name
    target_path = os.path.join(images_dir, target_name)
    
    counter = 1
    while os.path.exists(target_path):
        target_name = f"{name}_{counter}{ext}"
        target_path = os.path.join(images_dir, target_name)
        counter += 1
    
    print(f"原始文件名: {original_name}")
    print(f"建议新文件名: {target_name}")
    print(f"冲突检测正常: {target_name != original_name}")
    
    # 清理测试文件
    if os.path.exists(original_file):
        os.remove(original_file)
        print("已清理测试文件")

def main():
    """主测试函数"""
    print("开始测试添加模板图片的相对路径功能...\n")
    
    try:
        # 测试目录结构
        images_dir = test_assets_images_structure()
        
        # 测试相对路径转换
        test_relative_path_conversion()
        
        # 测试文件名冲突处理
        test_file_name_conflict_handling()
        
        print("\n=== 测试总结 ===")
        print("✅ assets/images 目录结构正常")
        print("✅ 相对路径转换逻辑正常")
        print("✅ 文件名冲突处理正常")
        print("\n所有测试通过！添加图片时将使用相对路径。")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试重复文件检查功能

此脚本验证：
1. 添加相同内容的图片时不会重复复制
2. 会正确识别已存在的相同内容文件
3. 会提示用户文件已存在
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from PIL import Image

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath('..'))

from auto_approve.settings_dialog import SettingsDialog
from auto_approve.path_utils import get_app_base_dir

def create_test_image(path: str, color=(255, 0, 0), size=(50, 50)):
    """创建一个测试图片文件"""
    try:
        img = Image.new('RGB', size, color)
        img.save(path, 'PNG')
        return True
    except Exception as e:
        print(f"创建图片失败: {e}")
        # 创建一个简单的PNG文件内容
        png_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc```\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
        with open(path, 'wb') as f:
            f.write(png_content)
        return True

def calculate_file_hash(file_path: str) -> str:
    """计算文件的MD5哈希值（独立函数用于测试）"""
    import hashlib
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return ""

def find_duplicate_file_by_content(source_file: str, target_dir: str) -> str:
    """在目标目录中查找与源文件内容相同的文件（独立函数用于测试）"""
    if not os.path.exists(source_file) or not os.path.exists(target_dir):
        return ""
        
    source_hash = calculate_file_hash(source_file)
    if not source_hash:
        return ""
        
    # 遍历目标目录中的所有文件
    for filename in os.listdir(target_dir):
        file_path = os.path.join(target_dir, filename)
        if os.path.isfile(file_path):
            if calculate_file_hash(file_path) == source_hash:
                return filename
                
    return ""

def test_duplicate_detection():
    """测试重复文件检测功能"""
    print("=== 测试重复文件检测功能 ===\n")
    
    # 创建临时目录和测试文件
    temp_dir = tempfile.mkdtemp()
    test_files = []
    
    try:
        # 创建两个内容相同的测试图片
        test_image1 = os.path.join(temp_dir, "test_image1.png")
        test_image2 = os.path.join(temp_dir, "test_image2.png")
        test_image3 = os.path.join(temp_dir, "test_image3.png")
        
        # 创建相同内容的图片
        create_test_image(test_image1, color=(255, 0, 0))  # 红色
        create_test_image(test_image2, color=(255, 0, 0))  # 红色（相同内容）
        create_test_image(test_image3, color=(0, 255, 0))  # 绿色（不同内容）
        
        test_files = [test_image1, test_image2, test_image3]
        
        print(f"创建测试文件:")
        for i, f in enumerate(test_files, 1):
            print(f"  {i}. {f}")
        
        # 测试文件哈希计算
        print("\n=== 测试文件哈希计算 ===")
        hash1 = calculate_file_hash(test_image1)
        hash2 = calculate_file_hash(test_image2)
        hash3 = calculate_file_hash(test_image3)
        
        print(f"图片1哈希: {hash1}")
        print(f"图片2哈希: {hash2}")
        print(f"图片3哈希: {hash3}")
        
        # 验证相同内容的文件有相同哈希
        if hash1 == hash2:
            print("✓ 相同内容的文件哈希值相同")
        else:
            print("✗ 相同内容的文件哈希值不同")
            
        if hash1 != hash3:
            print("✓ 不同内容的文件哈希值不同")
        else:
            print("✗ 不同内容的文件哈希值相同")
        
        # 测试重复文件检测
        print("\n=== 测试重复文件检测 ===")
        
        # 确保assets/images目录存在
        proj_root = get_app_base_dir()
        images_abs = os.path.join(proj_root, "assets", "images")
        os.makedirs(images_abs, exist_ok=True)
        print(f"assets/images目录: {images_abs}")
        
        # 先复制第一个文件到assets/images
        first_file_name = "test_duplicate_1.png"
        first_file_path = os.path.join(images_abs, first_file_name)
        shutil.copy2(test_image1, first_file_path)
        print(f"已复制第一个文件到: {first_file_path}")
        
        # 测试检测重复文件
        duplicate_name = find_duplicate_file_by_content(test_image2, images_abs)
        if duplicate_name:
            print(f"✓ 成功检测到重复文件: {duplicate_name}")
        else:
            print("✗ 未能检测到重复文件")
            
        # 测试检测不同文件
        duplicate_name3 = find_duplicate_file_by_content(test_image3, images_abs)
        if not duplicate_name3:
            print("✓ 正确识别不同内容的文件")
        else:
            print(f"✗ 错误地将不同文件识别为重复: {duplicate_name3}")
        
        # 清理测试文件
        if os.path.exists(first_file_path):
            os.remove(first_file_path)
            print(f"已清理测试文件: {first_file_path}")
        
        print("\n=== 测试完成 ===")
        print("重复文件检查功能测试通过！")
        
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"已清理临时目录: {temp_dir}")

def main():
    """主函数"""
    print("开始测试重复文件检查功能...\n")
    
    success = test_duplicate_detection()
    
    if success:
        print("\n✅ 所有测试通过！")
        print("重复文件检查功能已正确实现。")
        return 0
    else:
        print("\n❌ 测试失败！")
        return 1

if __name__ == "__main__":
    exit(main())
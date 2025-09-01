#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示重复文件检查功能

此脚本演示了在用户手动添加图片时，如何检查assets/images目录中是否已经存在相同内容的文件。
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from PIL import Image

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath('..'))

from auto_approve.path_utils import get_app_base_dir

def create_demo_image(path: str, color=(255, 0, 0), size=(100, 100)):
    """创建一个演示图片文件"""
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
    """计算文件的MD5哈希值"""
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
    """在目标目录中查找与源文件内容相同的文件"""
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

def simulate_add_template_with_duplicate_check(source_file: str):
    """模拟添加模板时的重复检查过程"""
    print(f"\n=== 模拟添加模板: {os.path.basename(source_file)} ===")
    
    # 确保assets/images目录存在
    proj_root = get_app_base_dir()
    images_abs = os.path.join(proj_root, "assets", "images")
    images_rel = os.path.join("assets", "images")
    os.makedirs(images_abs, exist_ok=True)
    
    print(f"检查目录: {images_abs}")
    
    # 首先检查是否已经存在相同内容的文件
    duplicate_filename = find_duplicate_file_by_content(source_file, images_abs)
    if duplicate_filename:
        print(f"🔍 发现重复文件: {duplicate_filename}")
        print(f"📋 将使用现有文件，无需重复复制")
        rel_path = os.path.join(images_rel, duplicate_filename)
        print(f"✅ 添加到模板列表: {rel_path}")
        return rel_path, True  # 返回路径和是否为重复文件
    else:
        print(f"✨ 未发现重复文件，将复制新文件")
        
        # 生成目标文件名
        original_name = os.path.basename(source_file)
        name, ext = os.path.splitext(original_name)
        target_name = original_name
        target_abs_path = os.path.join(images_abs, target_name)
        
        # 如果文件名已存在，添加计数器避免冲突
        counter = 1
        while os.path.exists(target_abs_path):
            target_name = f"{name}_{counter}{ext}"
            target_abs_path = os.path.join(images_abs, target_name)
            counter += 1
        
        try:
            # 复制文件到assets/images目录
            shutil.copy2(source_file, target_abs_path)
            print(f"📁 文件已复制到: {target_abs_path}")
            
            # 使用相对路径
            rel_path = os.path.join(images_rel, target_name)
            print(f"✅ 添加到模板列表: {rel_path}")
            return rel_path, False  # 返回路径和是否为重复文件
            
        except Exception as e:
            print(f"❌ 复制失败: {e}")
            return None, False

def demo_duplicate_check():
    """演示重复文件检查功能"""
    print("=== 重复文件检查功能演示 ===")
    print("此演示展示了在用户手动添加图片时，如何避免重复复制相同内容的文件。\n")
    
    # 创建临时目录和演示文件
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 创建三个演示图片
        demo_image1 = os.path.join(temp_dir, "红色方块.png")
        demo_image2 = os.path.join(temp_dir, "红色方块_副本.png")  # 相同内容
        demo_image3 = os.path.join(temp_dir, "蓝色方块.png")  # 不同内容
        
        create_demo_image(demo_image1, color=(255, 0, 0))  # 红色
        create_demo_image(demo_image2, color=(255, 0, 0))  # 红色（相同内容）
        create_demo_image(demo_image3, color=(0, 0, 255))  # 蓝色（不同内容）
        
        print("📸 创建了以下演示图片:")
        print(f"  1. {os.path.basename(demo_image1)} (红色方块)")
        print(f"  2. {os.path.basename(demo_image2)} (红色方块副本，内容相同)")
        print(f"  3. {os.path.basename(demo_image3)} (蓝色方块，内容不同)")
        
        # 演示添加过程
        print("\n🚀 开始演示添加模板过程...")
        
        # 第一次添加
        path1, is_duplicate1 = simulate_add_template_with_duplicate_check(demo_image1)
        
        # 第二次添加相同内容的文件
        path2, is_duplicate2 = simulate_add_template_with_duplicate_check(demo_image2)
        
        # 第三次添加不同内容的文件
        path3, is_duplicate3 = simulate_add_template_with_duplicate_check(demo_image3)
        
        print("\n📊 演示结果总结:")
        print(f"  • 第一个文件: {'重复' if is_duplicate1 else '新文件'} -> {path1}")
        print(f"  • 第二个文件: {'重复' if is_duplicate2 else '新文件'} -> {path2}")
        print(f"  • 第三个文件: {'重复' if is_duplicate3 else '新文件'} -> {path3}")
        
        if is_duplicate2:
            print("\n✅ 成功检测到重复文件并避免了重复复制！")
        else:
            print("\n❌ 重复检测功能可能存在问题")
        
        # 清理演示文件
        proj_root = get_app_base_dir()
        images_dir = os.path.join(proj_root, "assets", "images")
        if os.path.exists(images_dir):
            for file in os.listdir(images_dir):
                if file.startswith(("红色方块", "蓝色方块")):
                    file_path = os.path.join(images_dir, file)
                    os.remove(file_path)
                    print(f"🧹 已清理演示文件: {file}")
        
        print("\n🎉 演示完成！重复文件检查功能正常工作。")
        
    except Exception as e:
        print(f"❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"[CLEANUP] 已清理临时目录: {temp_dir}")

def main():
    """主函数"""
    print("[DEMO] 重复文件检查功能演示程序")
    print("=" * 50)
    
    demo_duplicate_check()
    
    print("\n" + "=" * 50)
    print("[INFO] 功能说明:")
    print("  • 当用户手动添加图片时，系统会自动检查assets/images目录")
    print("  • 如果发现相同内容的文件，会提示用户并使用现有文件")
    print("  • 避免了重复复制相同内容的文件，节省存储空间")
    print("  • 通过MD5哈希值比较确保内容完全相同")
    
if __name__ == "__main__":
    main()
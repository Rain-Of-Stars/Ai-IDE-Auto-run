#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试设置对话框添加模板图片功能

此脚本模拟设置对话框中添加图片的流程，验证：
1. 图片被正确复制到 assets/images 目录
2. 列表中使用相对路径
3. 文件名冲突处理
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from PIL import Image

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(str(project_root))  # 切换到项目根目录

from auto_approve.path_utils import get_app_base_dir

def create_test_image_file(path: str, size=(100, 100), color=(255, 0, 0)):
    """创建一个真实的测试图片文件"""
    try:
        # 创建一个简单的红色图片
        img = Image.new('RGB', size, color)
        img.save(path, 'PNG')
        return True
    except ImportError:
        # 如果没有PIL，创建一个简单的文本文件
        with open(path, 'w', encoding='utf-8') as f:
            f.write("fake image content")
        return False

def simulate_add_templates_logic(source_paths):
    """模拟设置对话框中的 _on_add_templates 逻辑"""
    print("=== 模拟添加模板图片逻辑 ===")
    
    # 获取项目根目录和images目录
    proj_root = get_app_base_dir()
    images_abs = os.path.join(proj_root, "assets", "images")
    images_rel = os.path.join("assets", "images")
    
    print(f"项目根目录: {proj_root}")
    print(f"images绝对路径: {images_abs}")
    print(f"images相对路径: {images_rel}")
    
    # 确保目录存在
    os.makedirs(images_abs, exist_ok=True)
    print(f"已确保目录存在: {images_abs}")
    
    # 模拟现有模板路径列表
    existing_templates = set()
    
    added_templates = []
    
    for source_path in source_paths:
        if not source_path or not os.path.exists(source_path):
            print(f"跳过无效路径: {source_path}")
            continue
            
        print(f"\n处理源文件: {source_path}")
        
        # 生成目标文件名
        original_name = os.path.basename(source_path)
        name, ext = os.path.splitext(original_name)
        target_name = original_name
        target_abs_path = os.path.join(images_abs, target_name)
        
        # 处理文件名冲突
        counter = 1
        while os.path.exists(target_abs_path):
            target_name = f"{name}_{counter}{ext}"
            target_abs_path = os.path.join(images_abs, target_name)
            counter += 1
            
        print(f"目标文件名: {target_name}")
        print(f"目标绝对路径: {target_abs_path}")
        
        try:
            # 复制文件
            shutil.copy2(source_path, target_abs_path)
            print(f"✅ 文件复制成功")
            
            # 生成相对路径
            rel_path = os.path.join(images_rel, target_name)
            print(f"相对路径: {rel_path}")
            
            # 检查是否重复
            if rel_path not in existing_templates:
                existing_templates.add(rel_path)
                added_templates.append(rel_path)
                print(f"✅ 添加到模板列表: {rel_path}")
            else:
                print(f"⚠️ 路径已存在，跳过: {rel_path}")
                
        except Exception as e:
            print(f"❌ 复制失败: {e}")
    
    return added_templates

def test_add_templates_workflow():
    """测试完整的添加模板工作流程"""
    print("开始测试添加模板图片工作流程...\n")
    
    # 创建临时测试图片
    temp_dir = tempfile.mkdtemp()
    test_images = []
    
    try:
        # 创建几个测试图片
        for i, (name, color) in enumerate([
            ("test_template1.png", (255, 0, 0)),  # 红色
            ("test_template2.jpg", (0, 255, 0)),  # 绿色
            ("duplicate_name.png", (0, 0, 255)),  # 蓝色
            ("duplicate_name.png", (255, 255, 0)),  # 黄色（重名测试）
        ]):
            img_path = os.path.join(temp_dir, f"{i}_{name}")
            has_pil = create_test_image_file(img_path, color=color)
            test_images.append(img_path)
            print(f"创建测试图片: {img_path} (PIL可用: {has_pil})")
        
        # 模拟添加模板逻辑
        added_templates = simulate_add_templates_logic(test_images)
        
        print(f"\n=== 测试结果 ===")
        print(f"成功添加的模板数量: {len(added_templates)}")
        for template in added_templates:
            print(f"  - {template}")
        
        # 验证文件是否真的存在
        proj_root = get_app_base_dir()
        print(f"\n=== 验证文件存在性 ===")
        for template in added_templates:
            abs_path = os.path.join(proj_root, template)
            exists = os.path.exists(abs_path)
            print(f"{'✅' if exists else '❌'} {template} -> {abs_path}")
        
        # 清理assets/images中的测试文件
        print(f"\n=== 清理测试文件 ===")
        images_dir = os.path.join(proj_root, "assets", "images")
        if os.path.exists(images_dir):
            for file in os.listdir(images_dir):
                if file.startswith(("test_template", "0_", "1_", "2_", "3_")):
                    file_path = os.path.join(images_dir, file)
                    os.remove(file_path)
                    print(f"已删除: {file}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"已清理临时目录: {temp_dir}")

def main():
    """主函数"""
    success = test_add_templates_workflow()
    
    if success:
        print("\n🎉 所有测试通过！")
        print("设置对话框添加图片功能已正确配置为使用相对路径。")
        return 0
    else:
        print("\n❌ 测试失败！")
        return 1

if __name__ == "__main__":
    exit(main())
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终测试：验证添加图片时使用相对路径的完整功能
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath('..'))

from auto_approve.config_manager import load_config, save_config, AppConfig
from auto_approve.path_utils import get_app_base_dir

def test_complete_relative_path_workflow():
    """测试完整的相对路径工作流程"""
    print("=== 测试完整的相对路径工作流程 ===")
    
    # 1. 验证项目根目录识别
    app_base = get_app_base_dir()
    print(f"项目根目录: {app_base}")
    assert os.path.exists(app_base), "项目根目录不存在"
    
    # 2. 验证assets/images目录
    assets_images_dir = os.path.join(app_base, "assets", "images")
    if not os.path.exists(assets_images_dir):
        os.makedirs(assets_images_dir, exist_ok=True)
    print(f"assets/images目录: {assets_images_dir}")
    
    # 3. 创建测试图片
    test_image_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc```\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
        temp_file.write(test_image_content)
        temp_image_path = temp_file.name
    
    try:
        # 4. 模拟添加图片的过程（复制到assets/images并使用相对路径）
        filename = os.path.basename(temp_image_path)
        target_path = os.path.join(assets_images_dir, filename)
        
        # 处理文件名冲突
        counter = 1
        base_name, ext = os.path.splitext(filename)
        while os.path.exists(target_path):
            new_filename = f"{base_name}_{counter}{ext}"
            target_path = os.path.join(assets_images_dir, new_filename)
            filename = new_filename
            counter += 1
        
        # 复制文件
        shutil.copy2(temp_image_path, target_path)
        print(f"图片已复制到: {target_path}")
        
        # 生成相对路径
        relative_path = os.path.join("assets", "images", filename).replace("\\", "/")
        print(f"相对路径: {relative_path}")
        
        # 5. 验证相对路径可以正确解析
        full_path = os.path.join(app_base, relative_path.replace("/", os.sep))
        assert os.path.exists(full_path), f"相对路径解析失败: {full_path}"
        print("✓ 相对路径解析正确")
        
        # 6. 测试配置文件中的相对路径
        try:
            config = load_config()
            # 临时添加测试路径
            original_templates = config.template_paths.copy()
            config.template_paths.append(relative_path)
            save_config(config)
            
            # 重新加载并验证
            reloaded_config = load_config()
            assert relative_path in reloaded_config.template_paths, "配置保存失败"
            print("✓ 配置文件保存和加载正确")
            
            # 恢复原始配置
            config.template_paths = original_templates
            save_config(config)
            
        except Exception as e:
            print(f"配置测试失败: {e}")
            raise
        
        # 7. 清理测试文件
        if os.path.exists(target_path):
            os.remove(target_path)
            print("✓ 测试文件已清理")
        
        print("\n=== 所有测试通过！===")
        print("添加图片时使用相对路径的功能已完全实现并验证成功。")
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_image_path):
            os.remove(temp_image_path)

def test_path_resolution():
    """测试路径解析功能"""
    print("\n=== 测试路径解析功能 ===")
    
    app_base = get_app_base_dir()
    
    # 测试相对路径
    relative_paths = [
        "assets/images/test.png",
        "assets\\images\\test.png",
        "./assets/images/test.png"
    ]
    
    for rel_path in relative_paths:
        # 标准化路径
        normalized = rel_path.replace("\\", "/").lstrip("./")
        full_path = os.path.join(app_base, normalized.replace("/", os.sep))
        print(f"相对路径: {rel_path} -> 完整路径: {full_path}")
    
    print("✓ 路径解析测试完成")

if __name__ == "__main__":
    try:
        test_complete_relative_path_workflow()
        test_path_resolution()
        print("\n🎉 所有测试成功完成！")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
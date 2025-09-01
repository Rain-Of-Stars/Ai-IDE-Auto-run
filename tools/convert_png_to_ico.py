#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PNG转ICO格式转换工具
将PNG图片转换为ICO图标格式
"""

from PIL import Image
import os

def convert_png_to_ico(png_path, ico_path):
    """
    将PNG文件转换为高质量ICO文件
    
    Args:
        png_path (str): 源PNG文件路径
        ico_path (str): 目标ICO文件路径
    """
    try:
        # 打开PNG图片
        with Image.open(png_path) as img:
            print(f"源图片信息: {img.size}, 模式: {img.mode}")
            
            # 确保图片是RGBA模式（支持透明度）
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # 只使用原图尺寸，不改变PNG格式大小
            original_size = img.size
            sizes = [original_size]
            print(f"使用原图尺寸: {original_size[0]}x{original_size[1]}")
            
            # 直接使用原图，不进行任何处理
            print(f"保持原图质量: {original_size[0]}x{original_size[1]}")
            icon_images = [img.copy()]
            
            # 保存为ICO文件，使用最高质量设置
            # 对于单个图像，直接保存为ICO格式
            icon_images[0].save(
                ico_path,
                format='ICO',
                # 使用PNG压缩以获得更好的质量
                bitmap_format='png'
            )
            
        print(f"高质量转换成功: {png_path} -> {ico_path}")
        return True
        
    except Exception as e:
        print(f"转换失败: {e}")
        return False

def main():
    """
    主函数
    """
    # 定义文件路径
    png_file = "assets\\icons\\icons\\custom_icon_test.png"
    ico_file = "assets\\icons\\icons\\custom_icon.ico"
    
    # 检查源文件是否存在
    if not os.path.exists(png_file):
        print(f"错误: 源文件不存在 - {png_file}")
        return
    
    # 确保目标目录存在
    ico_dir = os.path.dirname(ico_file)
    if not os.path.exists(ico_dir):
        os.makedirs(ico_dir)
        print(f"创建目录: {ico_dir}")
    
    # 执行转换
    print(f"开始转换: {png_file} -> {ico_file}")
    success = convert_png_to_ico(png_file, ico_file)
    
    if success:
        print("转换完成!")
        # 显示文件信息
        if os.path.exists(ico_file):
            file_size = os.path.getsize(ico_file)
            print(f"生成的ICO文件大小: {file_size} 字节")
    else:
        print("转换失败!")

if __name__ == "__main__":
    main()
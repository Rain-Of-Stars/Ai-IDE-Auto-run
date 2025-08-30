#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
详细的坐标调试脚本
用于验证点击坐标计算是否正确
"""

import json
import mss
import cv2
import numpy as np
from pathlib import Path

def load_config():
    """加载配置文件"""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 加载配置失败: {e}")
        return None

def get_monitor_info():
    """获取显示器信息"""
    try:
        with mss.mss() as sct:
            monitors = sct.monitors
            return monitors
    except Exception as e:
        print(f"❌ 获取显示器信息失败: {e}")
        return None

def capture_screen(monitor_index, monitors):
    """截取指定屏幕"""
    try:
        with mss.mss() as sct:
            if monitor_index >= len(monitors):
                print(f"❌ 显示器索引 {monitor_index} 超出范围")
                return None
            
            monitor = monitors[monitor_index]
            screenshot = sct.grab(monitor)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img, monitor
    except Exception as e:
        print(f"❌ 截屏失败: {e}")
        return None, None

def find_template_in_image(img, template_path, threshold=0.7):
    """在图像中查找模板"""
    try:
        # 尝试使用相对路径
        if not Path(template_path).exists():
            # 尝试只使用文件名
            template_name = Path(template_path).name
            if Path(template_name).exists():
                template_path = template_name
                print(f"使用相对路径: {template_path}")
            else:
                print(f"❌ 模板文件不存在: {template_path}")
                return None
        
        # 使用cv2.imdecode来避免路径编码问题
        try:
            with open(template_path, 'rb') as f:
                file_bytes = np.frombuffer(f.read(), np.uint8)
                template = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        except:
            template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            
        if template is None:
            print(f"❌ 无法加载模板图像: {template_path}")
            return None
        
        # 转换为灰度图进行匹配
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        
        # 模板匹配
        result = cv2.matchTemplate(img_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        
        matches = []
        for pt in zip(*locations[::-1]):
            confidence = result[pt[1], pt[0]]
            matches.append({
                'x': pt[0],
                'y': pt[1],
                'confidence': confidence,
                'template_width': template.shape[1],
                'template_height': template.shape[0]
            })
        
        return matches
    except Exception as e:
        print(f"❌ 模板匹配失败: {e}")
        return None

def calculate_click_coordinates(match, monitor, config):
    """计算点击坐标"""
    try:
        # 模板中心点相对坐标
        template_center_x = match['x'] + match['template_width'] // 2
        template_center_y = match['y'] + match['template_height'] // 2
        
        print(f"  模板在屏幕中的位置: ({match['x']}, {match['y']})")
        print(f"  模板尺寸: {match['template_width']} x {match['template_height']}")
        print(f"  模板中心点(屏幕相对): ({template_center_x}, {template_center_y})")
        
        # 应用点击偏移
        click_offset = config.get('click_offset', [0.0, 0.0])
        offset_x = template_center_x + click_offset[0]
        offset_y = template_center_y + click_offset[1]
        
        print(f"  点击偏移: {click_offset}")
        print(f"  应用偏移后(屏幕相对): ({offset_x}, {offset_y})")
        
        # 转换为全局坐标
        coordinate_transform_mode = config.get('coordinate_transform_mode', 'auto')
        
        if coordinate_transform_mode == 'absolute':
            # 绝对坐标模式：直接加上显示器的左上角坐标
            global_x = monitor['left'] + offset_x
            global_y = monitor['top'] + offset_y
        else:
            # 其他模式的处理
            global_x = monitor['left'] + offset_x
            global_y = monitor['top'] + offset_y
        
        print(f"  显示器偏移: ({monitor['left']}, {monitor['top']})")
        print(f"  最终全局坐标: ({global_x}, {global_y})")
        
        # 应用坐标校正
        coordinate_offset = config.get('coordinate_offset', [0, 0])
        final_x = global_x + coordinate_offset[0]
        final_y = global_y + coordinate_offset[1]
        
        print(f"  坐标校正: {coordinate_offset}")
        print(f"  最终点击坐标: ({final_x}, {final_y})")
        
        return {
            'screen_relative': (template_center_x, template_center_y),
            'with_offset': (offset_x, offset_y),
            'global_coords': (global_x, global_y),
            'final_coords': (final_x, final_y)
        }
    except Exception as e:
        print(f"❌ 坐标计算失败: {e}")
        return None

def validate_coordinates(coords, monitors):
    """验证坐标是否在有效范围内"""
    final_x, final_y = coords['final_coords']
    
    # 检查是否在虚拟屏幕范围内
    virtual_screen = monitors[0]
    virtual_left = virtual_screen['left']
    virtual_top = virtual_screen['top']
    virtual_right = virtual_left + virtual_screen['width']
    virtual_bottom = virtual_top + virtual_screen['height']
    
    in_virtual = (virtual_left <= final_x < virtual_right and 
                  virtual_top <= final_y < virtual_bottom)
    
    print(f"  虚拟屏幕范围: ({virtual_left}, {virtual_top}) 到 ({virtual_right}, {virtual_bottom})")
    print(f"  坐标在虚拟屏幕内: {in_virtual}")
    
    # 检查在哪个物理屏幕内
    for i, monitor in enumerate(monitors[1:], 1):
        left = monitor['left']
        top = monitor['top']
        right = left + monitor['width']
        bottom = top + monitor['height']
        
        in_monitor = (left <= final_x < right and top <= final_y < bottom)
        print(f"  屏幕{i}范围: ({left}, {top}) 到 ({right}, {bottom}) - 坐标在内: {in_monitor}")
    
    return in_virtual

def debug_coordinates():
    """主调试函数"""
    print("=== 坐标调试开始 ===")
    
    # 加载配置
    config = load_config()
    if not config:
        return
    
    print(f"✅ 配置加载成功")
    print(f"当前配置:")
    print(f"  monitor_index: {config.get('monitor_index', 1)}")
    print(f"  template_path: {config.get('template_path', '')}")
    print(f"  threshold: {config.get('threshold', 0.7)}")
    print(f"  click_offset: {config.get('click_offset', [0.0, 0.0])}")
    print(f"  coordinate_offset: {config.get('coordinate_offset', [0, 0])}")
    print(f"  coordinate_transform_mode: {config.get('coordinate_transform_mode', 'auto')}")
    print(f"  enable_multi_screen_polling: {config.get('enable_multi_screen_polling', True)}")
    
    # 获取显示器信息
    monitors = get_monitor_info()
    if not monitors:
        return
    
    print(f"\n=== 显示器信息 ===")
    for i, monitor in enumerate(monitors):
        if i == 0:
            print(f"虚拟屏幕: {monitor}")
        else:
            print(f"屏幕{i}: {monitor}")
    
    # 获取目标显示器
    monitor_index = config.get('monitor_index', 1)
    if monitor_index >= len(monitors):
        print(f"❌ 显示器索引 {monitor_index} 超出范围")
        return
    
    target_monitor = monitors[monitor_index]
    print(f"\n=== 目标显示器 ===")
    print(f"使用显示器{monitor_index}: {target_monitor}")
    
    # 截取屏幕
    print(f"\n=== 截取屏幕 ===")
    img, monitor = capture_screen(monitor_index, monitors)
    if img is None:
        return
    
    print(f"✅ 成功截取屏幕{monitor_index}，尺寸: {img.shape}")
    
    # 保存截图用于调试
    debug_screenshot_path = f"debug_screenshot_monitor_{monitor_index}.png"
    cv2.imwrite(debug_screenshot_path, img)
    print(f"✅ 调试截图已保存: {debug_screenshot_path}")
    
    # 查找模板
    template_path = config.get('template_path', '')
    threshold = config.get('threshold', 0.7)
    
    print(f"\n=== 模板匹配 ===")
    print(f"模板路径: {template_path}")
    print(f"匹配阈值: {threshold}")
    
    matches = find_template_in_image(img, template_path, threshold)
    if matches is None:
        return
    
    if not matches:
        print(f"❌ 未找到匹配的模板")
        return
    
    print(f"✅ 找到 {len(matches)} 个匹配")
    
    # 分析每个匹配的坐标
    for i, match in enumerate(matches):
        print(f"\n=== 匹配 {i+1} 坐标分析 ===")
        print(f"匹配置信度: {match['confidence']:.3f}")
        
        coords = calculate_click_coordinates(match, monitor, config)
        if coords:
            print(f"\n=== 坐标验证 ===")
            is_valid = validate_coordinates(coords, monitors)
            
            if is_valid:
                print(f"✅ 坐标有效")
            else:
                print(f"❌ 坐标无效")
            
            # 在截图上标记点击位置
            screen_x, screen_y = coords['screen_relative']
            cv2.circle(img, (int(screen_x), int(screen_y)), 10, (0, 255, 0), 2)
            cv2.putText(img, f"Match {i+1}", (int(screen_x)+15, int(screen_y)), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    
    # 保存标记后的截图
    marked_screenshot_path = f"debug_marked_monitor_{monitor_index}.png"
    cv2.imwrite(marked_screenshot_path, img)
    print(f"\n✅ 标记截图已保存: {marked_screenshot_path}")
    
    print(f"\n=== 调试完成 ===")
    print(f"请检查生成的调试图片以验证坐标计算是否正确")

if __name__ == "__main__":
    debug_coordinates()
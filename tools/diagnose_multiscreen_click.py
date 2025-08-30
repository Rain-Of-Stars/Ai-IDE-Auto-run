#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多屏幕点击问题诊断脚本

用于诊断为什么在屏幕1可以正确点击，但在屏幕2（主屏）无法正确点击的问题。
"""

import sys
import json
import mss
from pathlib import Path

def load_current_config():
    """加载当前配置"""
    config_file = Path("config.json")
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def analyze_screen_setup():
    """分析屏幕设置"""
    print("=== 屏幕设置分析 ===")
    
    with mss.mss() as sct:
        monitors = sct.monitors
        print(f"检测到 {len(monitors)} 个监视器（包括虚拟屏幕）")
        
        # 虚拟屏幕信息
        virtual = monitors[0]
        print(f"虚拟屏幕: {virtual}")
        
        # 实际屏幕信息
        for i, monitor in enumerate(monitors[1:], 1):
            is_primary = "是" if (monitor['left'] == 0 and monitor['top'] == 0) else "否"
            print(f"屏幕 {i}: {monitor}, 主屏: {is_primary}")
    
    return monitors

def test_coordinate_calculation(monitors):
    """测试坐标计算"""
    print("\n=== 坐标计算测试 ===")
    
    config = load_current_config()
    
    # 测试每个屏幕的中心点坐标
    for i, monitor in enumerate(monitors[1:], 1):
        center_x = monitor['left'] + monitor['width'] // 2
        center_y = monitor['top'] + monitor['height'] // 2
        
        print(f"\n屏幕 {i} 中心点坐标: ({center_x}, {center_y})")
        print(f"屏幕 {i} 范围: left={monitor['left']}, top={monitor['top']}, width={monitor['width']}, height={monitor['height']}")
        
        # 模拟坐标转换过程
        test_coordinate_transform(i, center_x, center_y, monitor, config)

def test_coordinate_transform(screen_num, x, y, monitor, config):
    """测试坐标转换过程"""
    print(f"\n--- 屏幕 {screen_num} 坐标转换测试 ---")
    
    print(f"原始坐标: ({x}, {y})")
    
    # 应用用户偏移
    click_offset = config.get('click_offset', [0, 0])
    offset_x = x + int(click_offset[0])
    offset_y = y + int(click_offset[1])
    print(f"应用用户偏移后: ({offset_x}, {offset_y}), 偏移量: {click_offset}")
    
    # 应用坐标校正
    enable_coordinate_correction = config.get('enable_coordinate_correction', False)
    if enable_coordinate_correction:
        coordinate_offset = config.get('coordinate_offset', [0, 0])
        final_x = offset_x + coordinate_offset[0]
        final_y = offset_y + coordinate_offset[1]
        print(f"应用坐标校正后: ({final_x}, {final_y}), 校正偏移: {coordinate_offset}")
    else:
        final_x, final_y = offset_x, offset_y
        print("坐标校正已禁用")
    
    # 验证最终坐标是否在虚拟屏幕范围内
    with mss.mss() as sct:
        virtual_screen = sct.monitors[0]
    
    in_virtual = (final_x >= virtual_screen['left'] and 
                  final_x < virtual_screen['left'] + virtual_screen['width'] and
                  final_y >= virtual_screen['top'] and 
                  final_y < virtual_screen['top'] + virtual_screen['height'])
    
    print(f"虚拟屏幕范围: {virtual_screen}")
    print(f"最终坐标在虚拟屏幕内: {'是' if in_virtual else '否'}")
    
    # 验证最终坐标是否在当前屏幕范围内
    in_current_screen = (final_x >= monitor['left'] and 
                        final_x < monitor['left'] + monitor['width'] and
                        final_y >= monitor['top'] and 
                        final_y < monitor['top'] + monitor['height'])
    
    print(f"最终坐标在当前屏幕内: {'是' if in_current_screen else '否'}")
    
    return final_x, final_y

def diagnose_config_issues():
    """诊断配置问题"""
    print("\n=== 配置诊断 ===")
    
    config = load_current_config()
    
    print(f"当前配置:")
    print(f"  monitor_index: {config.get('monitor_index', 1)}")
    print(f"  enable_multi_screen_polling: {config.get('enable_multi_screen_polling', False)}")
    print(f"  screen_polling_interval_ms: {config.get('screen_polling_interval_ms', 3000)}")
    print(f"  enable_coordinate_correction: {config.get('enable_coordinate_correction', False)}")
    print(f"  coordinate_offset: {config.get('coordinate_offset', [0, 0])}")
    print(f"  coordinate_transform_mode: {config.get('coordinate_transform_mode', 'absolute')}")
    print(f"  enhanced_window_finding: {config.get('enhanced_window_finding', False)}")
    print(f"  verify_window_before_click: {config.get('verify_window_before_click', False)}")
    print(f"  click_method: {config.get('click_method', 'post_message')}")
    print(f"  click_offset: {config.get('click_offset', [0, 0])}")
    
    # 检查可能的问题
    issues = []
    
    if config.get('enable_multi_screen_polling', False):
        issues.append("启用了多屏幕轮询，可能导致坐标计算混乱")
    
    coordinate_offset = config.get('coordinate_offset', [0, 0])
    if coordinate_offset != [0, 0]:
        issues.append(f"设置了坐标偏移 {coordinate_offset}，可能影响点击精度")
    
    monitor_index = config.get('monitor_index', 1)
    if monitor_index != 1:
        issues.append(f"monitor_index设置为 {monitor_index}，可能不是主屏")
    
    click_offset = config.get('click_offset', [0, 0])
    if click_offset != [0, 0]:
        issues.append(f"设置了点击偏移 {click_offset}，可能影响点击位置")
    
    if issues:
        print("发现潜在问题:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("配置看起来正常")
    
    return issues

def suggest_fixes(issues, monitors):
    """建议修复方案"""
    print("\n=== 修复建议 ===")
    
    if not issues:
        print("未发现明显的配置问题，但仍有以下建议:")
    
    # 找到主屏幕索引
    primary_screen_idx = 1
    for i, monitor in enumerate(monitors[1:], 1):
        if monitor['left'] == 0 and monitor['top'] == 0:
            primary_screen_idx = i
            break
    
    print(f"检测到主屏幕索引: {primary_screen_idx}")
    
    suggestions = [
        f"1. 将 monitor_index 设置为主屏幕索引: {primary_screen_idx}",
        "2. 禁用多屏幕轮询: enable_multi_screen_polling = false",
        "3. 重置坐标偏移: coordinate_offset = [0, 0]",
        "4. 重置点击偏移: click_offset = [0, 0]",
        "5. 启用调试模式以获取更多信息: debug_mode = true",
        "6. 使用绝对坐标模式: coordinate_transform_mode = 'absolute'",
        "7. 启用增强窗口查找: enhanced_window_finding = true",
        "8. 启用点击前窗口验证: verify_window_before_click = true"
    ]
    
    for suggestion in suggestions:
        print(suggestion)

def analyze_coordinate_differences():
    """分析不同屏幕间的坐标差异"""
    print("\n=== 屏幕坐标差异分析 ===")
    
    with mss.mss() as sct:
        monitors = sct.monitors[1:]  # 排除虚拟屏幕
        
        if len(monitors) < 2:
            print("只检测到一个屏幕，无法进行对比分析")
            return
        
        print("屏幕坐标系统分析:")
        for i, monitor in enumerate(monitors, 1):
            print(f"屏幕 {i}:")
            print(f"  左上角: ({monitor['left']}, {monitor['top']})")
            print(f"  右下角: ({monitor['left'] + monitor['width'] - 1}, {monitor['top'] + monitor['height'] - 1})")
            print(f"  中心点: ({monitor['left'] + monitor['width'] // 2}, {monitor['top'] + monitor['height'] // 2})")
            print(f"  尺寸: {monitor['width']} x {monitor['height']}")
            
            # 分析坐标特点
            if monitor['left'] == 0 and monitor['top'] == 0:
                print(f"  特点: 主屏幕（坐标原点）")
            elif monitor['left'] < 0:
                print(f"  特点: 位于主屏幕左侧，使用负坐标")
            elif monitor['left'] > 0:
                print(f"  特点: 位于主屏幕右侧，使用正坐标")
            print()

def main():
    """主函数"""
    print("开始多屏幕点击问题诊断...")
    print(f"Python版本: {sys.version}")
    
    try:
        # 1. 分析屏幕设置
        monitors = analyze_screen_setup()
        
        # 2. 分析坐标差异
        analyze_coordinate_differences()
        
        # 3. 测试坐标计算
        test_coordinate_calculation(monitors)
        
        # 4. 诊断配置问题
        issues = diagnose_config_issues()
        
        # 5. 提供修复建议
        suggest_fixes(issues, monitors)
        
        print("\n诊断完成！")
        
    except Exception as e:
        print(f"诊断过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
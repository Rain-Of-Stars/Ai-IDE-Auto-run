#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复多屏幕配置脚本

根据诊断结果修复多屏幕点击问题的配置。
"""

import json
import mss
from pathlib import Path
from datetime import datetime

def backup_config():
    """备份当前配置"""
    config_file = Path("config.json")
    if config_file.exists():
        backup_file = Path(f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"配置已备份到: {backup_file}")
        return config
    return {}

def detect_primary_screen():
    """检测主屏幕索引"""
    with mss.mss() as sct:
        monitors = sct.monitors[1:]  # 排除虚拟屏幕
        
        for i, monitor in enumerate(monitors, 1):
            if monitor['left'] == 0 and monitor['top'] == 0:
                return i, monitor
    
    # 如果没有找到主屏幕，返回第一个屏幕
    return 1, monitors[0] if monitors else None

def analyze_screen_layout():
    """分析屏幕布局"""
    print("=== 屏幕布局分析 ===")
    
    with mss.mss() as sct:
        monitors = sct.monitors
        virtual_screen = monitors[0]
        actual_screens = monitors[1:]
        
        print(f"虚拟屏幕: {virtual_screen}")
        print(f"实际屏幕数量: {len(actual_screens)}")
        
        primary_idx, primary_monitor = detect_primary_screen()
        print(f"主屏幕索引: {primary_idx}")
        print(f"主屏幕信息: {primary_monitor}")
        
        for i, monitor in enumerate(actual_screens, 1):
            is_primary = "是" if i == primary_idx else "否"
            position = "左侧" if monitor['left'] < 0 else "右侧" if monitor['left'] > 0 else "原点"
            print(f"屏幕 {i}: {monitor}, 主屏: {is_primary}, 位置: {position}")
        
        return primary_idx, actual_screens

def create_fixed_config(current_config, primary_idx):
    """创建修复后的配置"""
    print("\n=== 创建修复配置 ===")
    
    # 基于当前配置创建修复版本
    fixed_config = current_config.copy()
    
    # 修复关键设置
    changes = []
    
    # 1. 设置正确的主屏幕索引
    if fixed_config.get('monitor_index', 1) != primary_idx:
        old_value = fixed_config.get('monitor_index', 1)
        fixed_config['monitor_index'] = primary_idx
        changes.append(f"monitor_index: {old_value} -> {primary_idx}")
    
    # 2. 禁用多屏幕轮询（这是主要问题）
    if fixed_config.get('enable_multi_screen_polling', False):
        fixed_config['enable_multi_screen_polling'] = False
        changes.append("enable_multi_screen_polling: True -> False")
    
    # 3. 重置坐标偏移
    coordinate_offset = fixed_config.get('coordinate_offset', [0, 0])
    if coordinate_offset != [0, 0]:
        fixed_config['coordinate_offset'] = [0, 0]
        changes.append(f"coordinate_offset: {coordinate_offset} -> [0, 0]")
    
    # 4. 重置点击偏移
    click_offset = fixed_config.get('click_offset', [0, 0])
    if click_offset != [0, 0]:
        fixed_config['click_offset'] = [0, 0]
        changes.append(f"click_offset: {click_offset} -> [0, 0]")
    
    # 5. 设置为绝对坐标模式
    if fixed_config.get('coordinate_transform_mode', 'absolute') != 'absolute':
        old_mode = fixed_config.get('coordinate_transform_mode', 'auto')
        fixed_config['coordinate_transform_mode'] = 'absolute'
        changes.append(f"coordinate_transform_mode: {old_mode} -> absolute")
    
    # 6. 启用调试模式
    if not fixed_config.get('debug_mode', False):
        fixed_config['debug_mode'] = True
        changes.append("debug_mode: False -> True")
    
    # 7. 启用增强窗口查找
    if not fixed_config.get('enhanced_window_finding', False):
        fixed_config['enhanced_window_finding'] = True
        changes.append("enhanced_window_finding: False -> True")
    
    # 8. 启用点击前窗口验证
    if not fixed_config.get('verify_window_before_click', False):
        fixed_config['verify_window_before_click'] = True
        changes.append("verify_window_before_click: False -> True")
    
    if changes:
        print("将进行以下配置更改:")
        for change in changes:
            print(f"  - {change}")
    else:
        print("配置已经是最优状态，无需更改")
    
    return fixed_config, changes

def apply_fixed_config(fixed_config):
    """应用修复后的配置"""
    config_file = Path("config.json")
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(fixed_config, f, indent=2, ensure_ascii=False)
    
    print(f"\n修复后的配置已保存到: {config_file}")

def explain_problem():
    """解释问题原因"""
    print("\n=== 问题原因分析 ===")
    print("根据诊断结果，屏幕2无法正确点击的主要原因是:")
    print()
    print("1. **多屏幕轮询混乱**: enable_multi_screen_polling=True")
    print("   - 程序在扫描时会在不同屏幕间切换")
    print("   - 坐标计算基于当前轮询的屏幕，而不是目标检测的屏幕")
    print("   - 导致在屏幕2检测到目标，但用屏幕1的坐标系统计算点击位置")
    print()
    print("2. **屏幕坐标系统差异**:")
    print("   - 屏幕1: 位于左侧，坐标范围 (-2560, 0) 到 (0, 1600)")
    print("   - 屏幕2: 主屏幕，坐标范围 (0, 0) 到 (2560, 1440)")
    print("   - 两个屏幕的坐标系统完全不同")
    print()
    print("3. **配置不匹配**:")
    print("   - monitor_index=1 指向屏幕1（左侧屏幕）")
    print("   - 但实际主屏幕是屏幕2")
    print("   - 坐标转换模式设置为'auto'，增加了不确定性")
    print()
    print("**修复方案**:")
    print("- 禁用多屏幕轮询，固定使用主屏幕")
    print("- 将monitor_index设置为主屏幕索引")
    print("- 使用绝对坐标模式")
    print("- 重置所有坐标偏移")
    print("- 启用调试和增强功能")

def main():
    """主函数"""
    print("开始修复多屏幕配置...")
    
    try:
        # 1. 分析屏幕布局
        primary_idx, screens = analyze_screen_layout()
        
        # 2. 备份当前配置
        current_config = backup_config()
        
        # 3. 创建修复配置
        fixed_config, changes = create_fixed_config(current_config, primary_idx)
        
        # 4. 询问用户是否应用修复
        if changes:
            print("\n是否应用这些修复? (y/n): ", end="")
            response = input().strip().lower()
            
            if response in ['y', 'yes', '是', 'Y']:
                apply_fixed_config(fixed_config)
                print("\n✅ 配置修复完成！")
                print("\n请重启程序以使配置生效。")
            else:
                print("\n❌ 用户取消了配置修复。")
        
        # 5. 解释问题原因
        explain_problem()
        
    except Exception as e:
        print(f"修复过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
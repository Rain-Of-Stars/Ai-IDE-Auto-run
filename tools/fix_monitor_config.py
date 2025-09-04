# -*- coding: utf-8 -*-
"""
显示器配置修复工具
用于检查和修复config.json中的无效显示器索引
"""

import json
import os
import sys
from typing import List, Dict, Any

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def get_monitor_info():
    """获取当前系统的显示器信息"""
    try:
        from capture.monitor_utils import get_all_monitors_info
        monitors = get_all_monitors_info()
        return monitors
    except Exception as e:
        print(f"❌ 获取显示器信息失败: {e}")
        return []

def check_config():
    """检查配置文件中的显示器索引"""
    config_path = "config.json"
    
    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        return None, None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        monitor_index = config.get('monitor_index', 0)
        print(f"📋 当前配置的显示器索引: {monitor_index}")
        
        return config, monitor_index
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}")
        return None, None

def fix_config(config: Dict[str, Any], monitors: List[Dict[str, Any]]) -> bool:
    """修复配置文件中的显示器索引"""
    if not config or not monitors:
        return False
    
    current_index = config.get('monitor_index', 0)
    
    # 检查索引是否有效
    if 0 <= current_index < len(monitors):
        print(f"✅ 显示器索引 {current_index} 有效，无需修复")
        return True
    
    # 索引无效，需要修复
    print(f"⚠️  显示器索引 {current_index} 无效，有效范围: 0-{len(monitors)-1}")
    
    # 自动选择主显示器（索引0）
    new_index = 0
    config['monitor_index'] = new_index
    
    try:
        # 备份原配置文件
        backup_path = "config.json.backup"
        with open("config.json", 'r', encoding='utf-8') as f:
            backup_content = f.read()
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(backup_content)
        print(f"📁 已备份原配置文件到: {backup_path}")
        
        # 写入修复后的配置
        with open("config.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"🔧 已修复显示器索引: {current_index} → {new_index}")
        return True
        
    except Exception as e:
        print(f"❌ 修复配置文件失败: {e}")
        return False

def display_monitor_info(monitors: List[Dict[str, Any]]):
    """显示显示器信息"""
    print(f"\n📺 系统显示器信息 (共 {len(monitors)} 个):")
    print("-" * 60)
    
    for i, monitor in enumerate(monitors):
        width = monitor.get('width', 0)
        height = monitor.get('height', 0)
        left = monitor.get('left', 0)
        top = monitor.get('top', 0)
        is_primary = monitor.get('is_primary', False)
        device_name = monitor.get('device_name', 'Unknown')
        
        primary_mark = " [主显示器]" if is_primary else ""
        print(f"索引 {i}: {width}x{height} @ ({left}, {top}){primary_mark}")
        print(f"       设备: {device_name}")
        
        if i < len(monitors) - 1:
            print()

def main():
    """主函数"""
    print("显示器配置修复工具")
    print("=" * 50)
    
    # 1. 获取显示器信息
    print("1. 检查系统显示器...")
    monitors = get_monitor_info()
    
    if not monitors:
        print("❌ 无法获取显示器信息，请检查WGC环境")
        return
    
    display_monitor_info(monitors)
    
    # 2. 检查配置文件
    print("\n2. 检查配置文件...")
    config, monitor_index = check_config()
    
    if config is None:
        return
    
    # 3. 验证和修复
    print("\n3. 验证显示器索引...")
    
    if 0 <= monitor_index < len(monitors):
        print(f"✅ 显示器索引 {monitor_index} 有效")
        selected_monitor = monitors[monitor_index]
        print(f"✅ 对应显示器: {selected_monitor.get('width', 0)}x{selected_monitor.get('height', 0)}")
        if selected_monitor.get('is_primary', False):
            print("✅ 这是主显示器")
    else:
        print(f"❌ 显示器索引 {monitor_index} 无效")
        print("\n4. 自动修复...")
        
        if fix_config(config, monitors):
            print("✅ 配置修复完成")
            print("✅ 现在使用主显示器 (索引 0)")
        else:
            print("❌ 配置修复失败")
    
    print("\n" + "=" * 50)
    print("修复完成！建议重启应用程序以应用新配置。")

if __name__ == "__main__":
    main()

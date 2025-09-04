# -*- coding: utf-8 -*-
"""
UI性能修复工具 - 一键应用性能优化设置
解决UI卡顿问题，提升系统响应性
"""
import os
import json
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from auto_approve.config_manager import load_config, save_config

def apply_performance_optimizations():
    """应用性能优化设置"""
    print("🚀 开始应用UI性能优化设置...")
    
    try:
        # 加载当前配置
        config = load_config()
        
        # 记录原始设置
        original_settings = {
            'interval_ms': config.interval_ms,
            'enable_multi_screen_polling': getattr(config, 'enable_multi_screen_polling', False),
            'save_debug_images': config.save_debug_images,
            'debug_mode': config.debug_mode,
            'grayscale': config.grayscale,
            'enable_multiscale': getattr(config, 'enable_multiscale', False),
        }
        
        print("📋 当前设置:")
        for key, value in original_settings.items():
            print(f"  {key}: {value}")
        
        # 应用性能优化设置
        optimizations = {
            'interval_ms': max(1000, config.interval_ms),  # 最少1秒间隔
            'enable_multi_screen_polling': False,  # 禁用多屏轮询
            'save_debug_images': False,  # 禁用调试图片保存
            'debug_mode': False,  # 禁用调试模式
            'grayscale': True,  # 启用灰度匹配
            'enable_multiscale': False,  # 禁用多尺度匹配
            'enable_notifications': True,  # 保持通知开启
            'cooldown_s': max(2.0, getattr(config, 'cooldown_s', 1.0)),  # 增加冷却时间
        }
        
        print("\n⚡ 应用性能优化设置:")
        changes_made = []
        
        for key, value in optimizations.items():
            if hasattr(config, key):
                old_value = getattr(config, key)
                if old_value != value:
                    setattr(config, key, value)
                    changes_made.append(f"  {key}: {old_value} → {value}")
                    print(f"  ✓ {key}: {old_value} → {value}")
                else:
                    print(f"  - {key}: {value} (无变化)")
            else:
                setattr(config, key, value)
                changes_made.append(f"  {key}: 新增 → {value}")
                print(f"  ✓ {key}: 新增 → {value}")
        
        # 保存配置
        if changes_made:
            save_config(config)
            print(f"\n✅ 已应用 {len(changes_made)} 项优化设置")
            print("📝 变更详情:")
            for change in changes_made:
                print(change)
        else:
            print("\n✅ 配置已经是最优状态，无需修改")
        
        # 保存备份配置
        backup_file = "config_backup_before_performance_fix.json"
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(original_settings, f, indent=2, ensure_ascii=False)
        print(f"\n💾 原始配置已备份到: {backup_file}")
        
        print("\n🎯 性能优化建议:")
        print("  1. 重启程序以应用新配置")
        print("  2. 减少模板数量（保留最常用的3-5个）")
        print("  3. 优化模板图片尺寸（建议50x50像素以内）")
        print("  4. 如果仍有卡顿，可进一步增加扫描间隔")
        
        return True
        
    except Exception as e:
        print(f"❌ 应用性能优化失败: {e}")
        return False

def restore_from_backup():
    """从备份恢复配置"""
    backup_file = "config_backup_before_performance_fix.json"
    
    if not os.path.exists(backup_file):
        print(f"❌ 备份文件不存在: {backup_file}")
        return False
    
    try:
        print("🔄 从备份恢复配置...")
        
        # 读取备份配置
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_settings = json.load(f)
        
        # 加载当前配置
        config = load_config()
        
        # 恢复设置
        restored_count = 0
        for key, value in backup_settings.items():
            if hasattr(config, key):
                setattr(config, key, value)
                restored_count += 1
                print(f"  ✓ 恢复 {key}: {value}")
        
        # 保存配置
        save_config(config)
        print(f"\n✅ 已恢复 {restored_count} 项设置")
        print("🔄 请重启程序以应用恢复的配置")
        
        return True
        
    except Exception as e:
        print(f"❌ 恢复配置失败: {e}")
        return False

def show_performance_status():
    """显示当前性能状态"""
    try:
        config = load_config()
        
        print("📊 当前性能相关设置:")
        print(f"  扫描间隔: {config.interval_ms}ms")
        print(f"  多屏轮询: {'启用' if getattr(config, 'enable_multi_screen_polling', False) else '禁用'}")
        print(f"  调试图片: {'保存' if config.save_debug_images else '不保存'}")
        print(f"  调试模式: {'启用' if config.debug_mode else '禁用'}")
        print(f"  灰度匹配: {'启用' if config.grayscale else '禁用'}")
        print(f"  多尺度匹配: {'启用' if getattr(config, 'enable_multiscale', False) else '禁用'}")
        print(f"  冷却时间: {getattr(config, 'cooldown_s', 1.0)}秒")
        
        # 性能评估
        issues = []
        if config.interval_ms < 1000:
            issues.append("扫描间隔过短，可能导致高CPU占用")
        if getattr(config, 'enable_multi_screen_polling', False):
            issues.append("多屏轮询会增加系统负载")
        if config.save_debug_images:
            issues.append("调试图片保存会占用磁盘空间和IO")
        if config.debug_mode:
            issues.append("调试模式会产生大量日志输出")
        if not config.grayscale:
            issues.append("彩色匹配比灰度匹配消耗更多CPU")
        if getattr(config, 'enable_multiscale', False):
            issues.append("多尺度匹配会显著增加计算量")
        
        if issues:
            print("\n⚠ 发现的性能问题:")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
            print(f"\n💡 建议运行性能优化来解决这些问题")
        else:
            print("\n✅ 当前配置已优化，性能良好")
            
    except Exception as e:
        print(f"❌ 获取性能状态失败: {e}")

def main():
    """主函数"""
    print("🔧 UI性能修复工具")
    print("=" * 50)
    
    while True:
        print("\n请选择操作:")
        print("1. 应用性能优化设置")
        print("2. 显示当前性能状态")
        print("3. 从备份恢复配置")
        print("0. 退出")
        
        try:
            choice = input("\n请输入选择 (0-3): ").strip()
            
            if choice == '0':
                print("👋 再见！")
                break
            elif choice == '1':
                apply_performance_optimizations()
            elif choice == '2':
                show_performance_status()
            elif choice == '3':
                restore_from_backup()
            else:
                print("❌ 无效选择，请输入0-3之间的数字")
                
        except KeyboardInterrupt:
            print("\n\n👋 用户中断，再见！")
            break
        except Exception as e:
            print(f"❌ 操作失败: {e}")

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
性能优化主程序 - CPU占用优化解决方案
集成所有性能优化功能，提供一键优化和性能监控
"""
from __future__ import annotations
import os
import sys
import time
import argparse
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from auto_approve.config_manager import load_config, save_config
from auto_approve.config_optimizer import ConfigOptimizer, auto_optimize_config
from auto_approve.performance_monitor import show_performance_monitor
from auto_approve.logger_manager import get_logger, enable_file_logging


def print_banner():
    """打印程序横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    AI-IDE-Auto-Run                           ║
║                   性能优化解决方案                            ║
║                                                              ║
║  解决CPU占用高的问题，提供智能配置优化和性能监控              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def analyze_current_performance():
    """分析当前性能问题"""
    print("\n🔍 正在分析当前配置的性能问题...")
    
    try:
        config = load_config()
        issues = []
        
        # 检查模板数量
        template_count = len(config.template_paths) if config.template_paths else 1
        if template_count > 10:
            issues.append(f"❌ 模板数量过多: {template_count}个，建议减少到3-5个核心模板")
        
        # 检查多尺度匹配
        if config.multi_scale:
            scale_count = len(config.scales) if hasattr(config, 'scales') else 3
            issues.append(f"❌ 多尺度匹配已启用: {scale_count}个尺度，增加{scale_count}倍计算量")
        
        # 检查扫描间隔
        if config.interval_ms < 1000:
            issues.append(f"❌ 扫描间隔过短: {config.interval_ms}ms，建议至少1500ms")
        
        # 检查多屏幕轮询
        if getattr(config, 'enable_multi_screen_polling', False):
            issues.append("❌ 多屏幕轮询已启用，会显著增加CPU占用")
        
        # 检查调试模式
        if config.debug_mode:
            issues.append("❌ 调试模式已启用，会产生大量日志输出")
        
        # 检查后端选择
        backend = getattr(config, 'capture_backend', 'screen')
        if backend not in ['wgc']:
            issues.append(f"❌ 当前后端 '{backend}' 可能不是最优选择，建议使用 'wgc'")
        
        print(f"\n📊 性能分析结果:")
        print(f"   • 模板数量: {template_count}")
        print(f"   • 扫描间隔: {config.interval_ms}ms")
        print(f"   • 多尺度匹配: {'启用' if config.multi_scale else '禁用'}")
        print(f"   • 灰度匹配: {'启用' if config.grayscale else '禁用'}")
        print(f"   • 调试模式: {'启用' if config.debug_mode else '禁用'}")
        print(f"   • 捕获后端: {backend}")
        
        if issues:
            print(f"\n⚠️  发现 {len(issues)} 个性能问题:")
            for issue in issues:
                print(f"   {issue}")
        else:
            print("\n✅ 当前配置性能良好")
        
        return len(issues)
        
    except Exception as e:
        print(f"❌ 分析配置失败: {e}")
        return -1


def apply_quick_optimization():
    """应用快速优化"""
    print("\n🚀 正在应用快速性能优化...")
    
    try:
        # 备份当前配置
        current_config = load_config()
        timestamp = int(time.time())
        backup_path = f"config_backup_{timestamp}.json"
        save_config(current_config, backup_path)
        print(f"✅ 原配置已备份到: {backup_path}")
        
        # 应用快速优化
        optimizer = ConfigOptimizer()
        optimized_config = optimizer.generate_optimized_config(current_config)
        
        # 显示优化对比
        print(f"\n📈 优化对比:")
        print(f"   扫描间隔: {current_config.interval_ms}ms → {optimized_config.interval_ms}ms")
        print(f"   模板数量: {len(current_config.template_paths or [current_config.template_path])} → {len(optimized_config.template_paths or [optimized_config.template_path])}")
        print(f"   多尺度匹配: {'启用' if current_config.multi_scale else '禁用'} → {'启用' if optimized_config.multi_scale else '禁用'}")
        print(f"   调试模式: {'启用' if current_config.debug_mode else '禁用'} → {'启用' if optimized_config.debug_mode else '禁用'}")
        print(f"   最大FPS: {getattr(current_config, 'fps_max', 30)} → {getattr(optimized_config, 'fps_max', 10)}")
        
        # 保存优化配置
        save_config(optimized_config)
        print(f"✅ 优化配置已保存")
        
        return True
        
    except Exception as e:
        print(f"❌ 应用优化失败: {e}")
        return False


def show_optimization_tips():
    """显示优化建议"""
    tips = """
💡 CPU占用优化建议:

1. 🎯 模板优化
   • 只保留最常用的3-5个模板
   • 删除相似或重复的模板
   • 优化模板图片尺寸（建议50x50以内）

2. ⏱️ 扫描频率优化
   • 增加扫描间隔到1500-2000ms
   • 根据实际需求调整，不需要过于频繁

3. 🔧 算法优化
   • 启用灰度匹配（减少计算量）
   • 禁用多尺度匹配（除非必需）
   • 设置合适的ROI区域

4. 🖥️ 系统优化
   • 使用WGC后端（硬件加速）
   • 关闭调试模式和图片保存
   • 禁用多屏幕轮询（单屏环境）

5. 📊 监控调优
   • 使用性能监控工具观察实际效果
   • 根据CPU使用率动态调整参数
   • 定期清理缓存和日志文件
"""
    print(tips)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="AI-IDE-Auto-Run 性能优化工具")
    parser.add_argument('--analyze', action='store_true', help='分析当前性能问题')
    parser.add_argument('--optimize', action='store_true', help='应用自动优化')
    parser.add_argument('--monitor', action='store_true', help='启动性能监控')
    parser.add_argument('--tips', action='store_true', help='显示优化建议')
    parser.add_argument('--auto', action='store_true', help='一键自动优化')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    # 设置日志
    if args.verbose:
        enable_file_logging(True)
    
    print_banner()
    
    # 如果没有指定参数，显示交互式菜单
    if not any([args.analyze, args.optimize, args.monitor, args.tips, args.auto]):
        show_interactive_menu()
        return
    
    # 执行指定的操作
    if args.analyze:
        analyze_current_performance()
    
    if args.optimize or args.auto:
        if apply_quick_optimization():
            print("\n✅ 优化完成！建议重启程序以应用新配置。")
        else:
            print("\n❌ 优化失败，请检查日志。")
    
    if args.tips:
        show_optimization_tips()
    
    if args.monitor:
        print("\n📊 启动性能监控界面...")
        try:
            from PySide6 import QtWidgets
            app = QtWidgets.QApplication.instance()
            if app is None:
                app = QtWidgets.QApplication(sys.argv)
            
            monitor = show_performance_monitor()
            app.exec()
        except ImportError:
            print("❌ 无法启动图形界面，请确保已安装PySide6")
        except Exception as e:
            print(f"❌ 启动监控界面失败: {e}")


def show_interactive_menu():
    """显示交互式菜单"""
    while True:
        print("\n" + "="*60)
        print("🛠️  性能优化工具菜单")
        print("="*60)
        print("1. 🔍 分析当前性能问题")
        print("2. 🚀 应用自动优化")
        print("3. 📊 启动性能监控")
        print("4. 💡 查看优化建议")
        print("5. ⚡ 一键自动优化")
        print("0. 🚪 退出")
        print("="*60)
        
        try:
            choice = input("请选择操作 (0-5): ").strip()
            
            if choice == '0':
                print("👋 再见！")
                break
            elif choice == '1':
                analyze_current_performance()
            elif choice == '2':
                if apply_quick_optimization():
                    print("\n✅ 优化完成！建议重启程序以应用新配置。")
            elif choice == '3':
                print("\n📊 启动性能监控界面...")
                try:
                    from PySide6 import QtWidgets
                    app = QtWidgets.QApplication.instance()
                    if app is None:
                        app = QtWidgets.QApplication(sys.argv)
                    
                    monitor = show_performance_monitor()
                    app.exec()
                except ImportError:
                    print("❌ 无法启动图形界面，请确保已安装PySide6")
                except Exception as e:
                    print(f"❌ 启动监控界面失败: {e}")
            elif choice == '4':
                show_optimization_tips()
            elif choice == '5':
                print("\n⚡ 执行一键自动优化...")
                issues_count = analyze_current_performance()
                if issues_count > 0:
                    if apply_quick_optimization():
                        print("\n✅ 一键优化完成！建议重启程序以应用新配置。")
                        print("💡 提示：可以使用选项3启动性能监控来验证优化效果。")
                else:
                    print("\n✅ 当前配置已经很好，无需优化。")
            else:
                print("❌ 无效选择，请输入0-5之间的数字。")
                
        except KeyboardInterrupt:
            print("\n\n👋 用户中断，再见！")
            break
        except Exception as e:
            print(f"❌ 操作失败: {e}")


if __name__ == "__main__":
    main()

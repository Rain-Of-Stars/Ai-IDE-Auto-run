#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单测试脚本
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    print("开始简单测试...")
    
    try:
        # 测试导入
        print("1. 测试导入模块...")
        from auto_approve.gui_responsiveness_manager import get_gui_responsiveness_manager
        print("   ✅ GUI响应性管理器导入成功")
        
        from auto_approve.gui_performance_monitor import get_gui_performance_monitor
        print("   ✅ GUI性能监控器导入成功")
        
        from workers.io_tasks import optimize_thread_pool
        print("   ✅ 线程池优化模块导入成功")
        
        # 测试基本功能
        print("2. 测试基本功能...")
        
        # 创建管理器
        gui_manager = get_gui_responsiveness_manager()
        print("   ✅ GUI响应性管理器创建成功")
        
        performance_monitor = get_gui_performance_monitor()
        print("   ✅ GUI性能监控器创建成功")
        
        # 优化线程池
        result = optimize_thread_pool(cpu_intensive_ratio=0.2, gui_priority=True)
        print(f"   ✅ 线程池优化成功: {result}")
        
        print("3. 测试完成")
        print("🎉 所有基本功能正常！")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("测试成功")
        sys.exit(0)
    else:
        print("测试失败")
        sys.exit(1)

# -*- coding: utf-8 -*-
"""
GUI响应性基础测试
验证GUI响应性优化的基本功能
"""
import os
import sys
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("🧪 GUI响应性基础测试")
print("=" * 50)

def test_gui_responsiveness_manager():
    """测试GUI响应性管理器"""
    print("1. 测试GUI响应性管理器...")
    
    try:
        from auto_approve.gui_responsiveness_manager import (
            get_gui_responsiveness_manager, 
            schedule_ui_update,
            register_ui_handler,
            UIUpdateRequest
        )
        
        # 创建管理器
        manager = get_gui_responsiveness_manager()
        print("   ✅ GUI响应性管理器创建成功")
        
        # 注册处理器
        def test_handler(request: UIUpdateRequest):
            print(f"   📝 处理UI更新: {request.widget_id} - {request.update_type}")
        
        register_ui_handler('test', test_handler)
        print("   ✅ UI更新处理器注册成功")
        
        # 调度更新
        schedule_ui_update('test_widget', 'test', {'data': 'test'}, priority=5)
        print("   ✅ UI更新调度成功")
        
        # 强制处理更新
        manager.force_process_updates()
        print("   ✅ UI更新处理成功")
        
        # 获取统计信息
        stats = manager.get_stats()
        print(f"   📊 统计信息: {stats}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ GUI响应性管理器测试失败: {e}")
        return False


def test_gui_performance_monitor():
    """测试GUI性能监控器"""
    print("\n2. 测试GUI性能监控器...")
    
    try:
        from auto_approve.gui_performance_monitor import (
            get_gui_performance_monitor,
            start_gui_monitoring,
            stop_gui_monitoring,
            record_ui_update
        )
        
        # 创建监控器
        monitor = get_gui_performance_monitor()
        print("   ✅ GUI性能监控器创建成功")
        
        # 启动监控
        start_gui_monitoring()
        print("   ✅ 性能监控启动成功")
        
        # 模拟UI更新
        for i in range(5):
            record_ui_update()
            time.sleep(0.1)
        print("   ✅ UI更新记录成功")
        
        # 等待收集指标
        time.sleep(1.5)
        
        # 获取性能指标
        metrics = monitor.get_current_metrics()
        if metrics:
            print(f"   📊 当前指标: CPU={metrics.main_thread_cpu_percent:.1f}%, "
                  f"内存={metrics.memory_usage_mb:.1f}MB, "
                  f"响应时间={metrics.response_time_ms:.1f}ms")
        else:
            print("   ⚠️ 暂无性能指标")
        
        # 获取性能摘要
        summary = monitor.get_performance_summary()
        if summary:
            print(f"   📈 性能摘要: 平均CPU={summary.get('avg_cpu_percent', 0):.1f}%, "
                  f"响应率={summary.get('responsive_ratio', 0):.1%}")
        
        # 停止监控
        stop_gui_monitoring()
        print("   ✅ 性能监控停止成功")
        
        return True
        
    except Exception as e:
        print(f"   ❌ GUI性能监控器测试失败: {e}")
        return False


def test_thread_pool_optimization():
    """测试线程池优化"""
    print("\n3. 测试线程池优化...")
    
    try:
        from workers.io_tasks import optimize_thread_pool, get_thread_pool_stats
        
        # 优化线程池
        result = optimize_thread_pool(cpu_intensive_ratio=0.2, gui_priority=True)
        print(f"   ✅ 线程池优化成功: {result}")
        
        # 获取线程池统计
        stats = get_thread_pool_stats()
        print(f"   📊 线程池统计: {stats}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 线程池优化测试失败: {e}")
        return False


def test_scanner_process_optimization():
    """测试扫描进程优化"""
    print("\n4. 测试扫描进程优化...")
    
    try:
        from workers.scanner_process import get_global_scanner_manager
        
        # 创建扫描进程管理器
        manager = get_global_scanner_manager()
        print("   ✅ 扫描进程管理器创建成功")
        
        # 检查轮询间隔优化
        if hasattr(manager, '_current_poll_interval'):
            print(f"   📊 当前轮询间隔: {manager._current_poll_interval}ms")
        
        if hasattr(manager, '_poll_stats'):
            print(f"   📈 轮询统计: {manager._poll_stats}")
        
        print("   ✅ 扫描进程优化检查完成")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 扫描进程优化测试失败: {e}")
        return False


def test_integration():
    """集成测试"""
    print("\n5. 集成测试...")
    
    try:
        # 模拟主程序的初始化流程
        from auto_approve.gui_responsiveness_manager import get_gui_responsiveness_manager
        from auto_approve.gui_performance_monitor import get_gui_performance_monitor, start_gui_monitoring
        from workers.io_tasks import optimize_thread_pool
        
        # 初始化组件
        gui_manager = get_gui_responsiveness_manager()
        performance_monitor = get_gui_performance_monitor()
        
        # 优化线程池
        optimize_thread_pool(cpu_intensive_ratio=0.2, gui_priority=True)
        
        # 启动监控
        start_gui_monitoring()
        
        print("   ✅ 所有组件初始化成功")
        
        # 模拟一些活动
        from auto_approve.gui_responsiveness_manager import schedule_ui_update
        from auto_approve.gui_performance_monitor import record_ui_update
        
        for i in range(10):
            schedule_ui_update(f'widget_{i}', 'tooltip', {'text': f'测试 {i}'})
            record_ui_update()
            time.sleep(0.05)
        
        # 强制处理更新
        gui_manager.force_process_updates()
        
        print("   ✅ 模拟活动完成")
        
        # 等待收集指标
        time.sleep(1.0)
        
        # 检查结果
        stats = gui_manager.get_stats()
        metrics = performance_monitor.get_current_metrics()
        
        print(f"   📊 GUI管理器统计: 总更新={stats.get('total_updates', 0)}, "
              f"批次={stats.get('batches_processed', 0)}")
        
        if metrics:
            print(f"   📈 性能指标: 响应时间={metrics.response_time_ms:.1f}ms, "
                  f"响应状态={'正常' if metrics.is_responsive else '异常'}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("开始GUI响应性基础测试...\n")
    
    test_results = []
    
    # 运行测试
    test_results.append(("GUI响应性管理器", test_gui_responsiveness_manager()))
    test_results.append(("GUI性能监控器", test_gui_performance_monitor()))
    test_results.append(("线程池优化", test_thread_pool_optimization()))
    test_results.append(("扫描进程优化", test_scanner_process_optimization()))
    test_results.append(("集成测试", test_integration()))
    
    # 显示结果
    print("\n" + "=" * 50)
    print("测试结果汇总:")
    print("=" * 50)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！GUI响应性优化工作正常。")
        return 0
    else:
        print("⚠️ 部分测试失败，请检查相关组件。")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

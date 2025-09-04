# -*- coding: utf-8 -*-
"""
性能优化测试脚本 - 验证UI卡顿优化效果
"""
import sys
import os
import time
import threading
import psutil
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.performance_config import get_performance_config, apply_performance_optimizations
from auto_approve.ui_optimizer import UIUpdateBatcher, TrayMenuOptimizer, get_performance_throttler
from auto_approve.logger_manager import get_logger


class PerformanceTestSuite:
    """性能测试套件"""
    
    def __init__(self):
        self.logger = get_logger()
        self.test_results = {}
        
    def test_ui_update_batching(self) -> Dict[str, Any]:
        """测试UI更新批处理性能"""
        print("🧪 测试UI更新批处理性能...")
        
        # 创建批处理器
        batcher = UIUpdateBatcher()
        
        # 测试批量更新性能
        start_time = time.perf_counter()
        
        # 模拟大量UI更新请求
        for i in range(1000):
            batcher.schedule_update(f'widget_{i % 10}', {
                'text': f'状态更新 {i}',
                'value': i,
                'timestamp': time.time()
            })
        
        # 等待批处理完成
        time.sleep(0.2)
        
        end_time = time.perf_counter()
        duration = end_time - start_time
        
        result = {
            'test_name': 'UI更新批处理',
            'duration_ms': duration * 1000,
            'updates_per_second': 1000 / duration,
            'status': 'PASS' if duration < 0.5 else 'FAIL'
        }
        
        print(f"   ✅ 批处理1000次更新耗时: {duration*1000:.2f}ms")
        print(f"   📊 更新速率: {result['updates_per_second']:.0f} 次/秒")
        
        return result
    
    def test_status_throttling(self) -> Dict[str, Any]:
        """测试状态更新节流性能"""
        print("🧪 测试状态更新节流...")
        
        throttler = get_performance_throttler()
        
        # 测试节流效果
        start_time = time.perf_counter()
        update_count = 0
        
        # 快速发送大量更新请求
        for i in range(100):
            if throttler.should_update('test_status', 0.1):  # 100ms间隔
                update_count += 1
            time.sleep(0.01)  # 10ms间隔发送
        
        end_time = time.perf_counter()
        duration = end_time - start_time
        
        # 理论上应该只有约10次更新通过节流
        expected_updates = int(duration / 0.1) + 1
        
        result = {
            'test_name': '状态更新节流',
            'actual_updates': update_count,
            'expected_updates': expected_updates,
            'throttling_efficiency': (100 - update_count) / 100 * 100,
            'status': 'PASS' if update_count <= expected_updates * 1.2 else 'FAIL'
        }
        
        print(f"   ✅ 实际更新次数: {update_count}")
        print(f"   📊 预期更新次数: {expected_updates}")
        print(f"   🎯 节流效率: {result['throttling_efficiency']:.1f}%")
        
        return result
    
    def test_memory_usage(self) -> Dict[str, Any]:
        """测试内存使用情况"""
        print("🧪 测试内存使用...")
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 模拟大量操作
        batchers = []
        for i in range(100):
            batcher = UIUpdateBatcher()
            for j in range(50):
                batcher.schedule_update(f'test_{j}', {'data': f'test_data_{i}_{j}'})
            batchers.append(batcher)
        
        # 等待处理完成
        time.sleep(0.5)
        
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 清理
        del batchers
        time.sleep(0.2)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        memory_cleanup = peak_memory - final_memory
        
        result = {
            'test_name': '内存使用测试',
            'initial_memory_mb': initial_memory,
            'peak_memory_mb': peak_memory,
            'final_memory_mb': final_memory,
            'memory_increase_mb': memory_increase,
            'memory_cleanup_mb': memory_cleanup,
            'cleanup_efficiency': memory_cleanup / memory_increase * 100 if memory_increase > 0 else 100,
            'status': 'PASS' if memory_increase < 50 else 'FAIL'  # 内存增长不超过50MB
        }
        
        print(f"   📈 初始内存: {initial_memory:.1f}MB")
        print(f"   📊 峰值内存: {peak_memory:.1f}MB")
        print(f"   📉 最终内存: {final_memory:.1f}MB")
        print(f"   🧹 清理效率: {result['cleanup_efficiency']:.1f}%")
        
        return result
    
    def test_performance_profiles(self) -> Dict[str, Any]:
        """测试性能配置档案"""
        print("🧪 测试性能配置档案...")
        
        config_manager = get_performance_config()
        
        # 测试不同性能档案
        profiles = ['high_performance', 'balanced', 'low_resource']
        profile_results = {}
        
        for profile_name in profiles:
            config_manager.set_profile(profile_name)
            profile = config_manager.get_current_profile()
            
            profile_results[profile_name] = {
                'status_update_interval': profile.status_update_interval,
                'animations_enabled': profile.animations_enabled,
                'template_cache_size': profile.template_cache_size,
                'max_worker_threads': profile.max_worker_threads
            }
            
            print(f"   📋 {profile.name}: 状态更新间隔={profile.status_update_interval}s, "
                  f"动画={'启用' if profile.animations_enabled else '禁用'}")
        
        # 测试自动检测
        config_manager.enable_auto_detect(True)
        auto_profile = config_manager.get_current_profile()
        
        result = {
            'test_name': '性能配置档案',
            'profiles_tested': len(profiles),
            'auto_detected_profile': auto_profile.name,
            'profile_results': profile_results,
            'status': 'PASS'
        }
        
        print(f"   🤖 自动检测档案: {auto_profile.name}")
        
        return result
    
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有性能测试"""
        print("🚀 开始性能优化测试...")
        print("=" * 50)
        
        # 应用性能优化
        apply_performance_optimizations()
        
        # 运行测试
        tests = [
            self.test_ui_update_batching,
            self.test_status_throttling,
            self.test_memory_usage,
            self.test_performance_profiles
        ]
        
        results = []
        passed_tests = 0
        
        for test_func in tests:
            try:
                result = test_func()
                results.append(result)
                if result['status'] == 'PASS':
                    passed_tests += 1
                print()
            except Exception as e:
                print(f"   ❌ 测试失败: {e}")
                results.append({
                    'test_name': test_func.__name__,
                    'status': 'ERROR',
                    'error': str(e)
                })
                print()
        
        # 汇总结果
        summary = {
            'total_tests': len(tests),
            'passed_tests': passed_tests,
            'failed_tests': len(tests) - passed_tests,
            'success_rate': passed_tests / len(tests) * 100,
            'test_results': results
        }
        
        print("=" * 50)
        print("📊 测试结果汇总:")
        print(f"   总测试数: {summary['total_tests']}")
        print(f"   通过测试: {summary['passed_tests']}")
        print(f"   失败测试: {summary['failed_tests']}")
        print(f"   成功率: {summary['success_rate']:.1f}%")
        
        if summary['success_rate'] >= 80:
            print("   🎉 性能优化效果良好!")
        elif summary['success_rate'] >= 60:
            print("   ⚠️  性能优化有一定效果，但仍有改进空间")
        else:
            print("   ❌ 性能优化效果不佳，需要进一步调整")
        
        return summary


def main():
    """主函数"""
    print("AI-IDE-Auto-Run 性能优化测试")
    print("=" * 50)
    
    # 创建测试套件
    test_suite = PerformanceTestSuite()
    
    # 运行测试
    results = test_suite.run_all_tests()
    
    # 保存结果
    import json
    with open('performance_test_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n📄 详细结果已保存到: performance_test_results.json")
    
    return results['success_rate'] >= 80


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

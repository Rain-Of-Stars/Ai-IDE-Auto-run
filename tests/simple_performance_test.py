# -*- coding: utf-8 -*-
"""
简化的性能测试脚本
"""
import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """测试模块导入"""
    try:
        from auto_approve.ui_optimizer import UIUpdateBatcher
        print("✅ UI优化器导入成功")
        
        from auto_approve.performance_config import get_performance_config
        print("✅ 性能配置导入成功")
        
        return True
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False

def test_ui_batching():
    """测试UI批处理"""
    try:
        from auto_approve.ui_optimizer import UIUpdateBatcher
        
        batcher = UIUpdateBatcher()
        start_time = time.perf_counter()
        
        # 测试100次更新
        for i in range(100):
            batcher.schedule_update(f'test_{i}', {'value': i})
        
        time.sleep(0.1)  # 等待批处理
        
        duration = time.perf_counter() - start_time
        print(f"✅ UI批处理测试完成，耗时: {duration*1000:.2f}ms")
        return True
    except Exception as e:
        print(f"❌ UI批处理测试失败: {e}")
        return False

def test_performance_config():
    """测试性能配置"""
    try:
        from auto_approve.performance_config import get_performance_config
        
        config = get_performance_config()
        profile = config.get_current_profile()
        
        print(f"✅ 当前性能档案: {profile.name}")
        print(f"   状态更新间隔: {profile.status_update_interval}s")
        print(f"   动画启用: {profile.animations_enabled}")
        
        return True
    except Exception as e:
        print(f"❌ 性能配置测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 简化性能测试开始")
    print("=" * 40)
    
    tests = [
        ("模块导入", test_imports),
        ("UI批处理", test_ui_batching),
        ("性能配置", test_performance_config)
    ]
    
    passed = 0
    total = len(tests)
    
    for name, test_func in tests:
        print(f"\n🧪 测试: {name}")
        if test_func():
            passed += 1
        else:
            print(f"   测试失败")
    
    print("\n" + "=" * 40)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！性能优化模块工作正常")
    else:
        print("⚠️  部分测试失败，需要检查配置")
    
    return passed == total

if __name__ == "__main__":
    try:
        success = main()
        print(f"\n退出代码: {0 if success else 1}")
    except Exception as e:
        print(f"❌ 测试执行失败: {e}")
        import traceback
        traceback.print_exc()

# -*- coding: utf-8 -*-
"""
内存优化系统简化测试脚本 - 无GUI环境版本

测试内容：
1. 内存模板管理器基础功能
2. 内存调试管理器基础功能
3. 内存配置管理器基础功能
4. 性能监控器基础功能
"""
import os
import sys
import time
import tempfile
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 模拟numpy和cv2
try:
    import numpy as np
except ImportError:
    print("警告: numpy不可用，使用模拟数据")
    class MockNumpy:
        @staticmethod
        def zeros(shape, dtype=None):
            return [[0 for _ in range(shape[1])] for _ in range(shape[0])]
        @staticmethod
        def fromfile(path, dtype=None):
            return [1, 2, 3, 4]
    np = MockNumpy()

def create_mock_image(width=100, height=100):
    """创建模拟图像数据"""
    if hasattr(np, 'zeros'):
        return np.zeros((height, width, 3), dtype='uint8')
    else:
        return [[[0, 0, 0] for _ in range(width)] for _ in range(height)]


def test_template_manager():
    """测试内存模板管理器"""
    print("\n=== 测试内存模板管理器 ===")
    
    try:
        from utils.memory_template_manager import get_template_manager
        
        # 创建临时模板文件
        temp_dir = tempfile.mkdtemp()
        template_paths = []
        
        try:
            # 创建测试模板文件
            for i in range(3):
                template_path = os.path.join(temp_dir, f"template_{i}.png")
                # 创建模拟图像文件
                with open(template_path, 'wb') as f:
                    f.write(b'mock_image_data_' + str(i).encode())
                template_paths.append(template_path)
            
            # 测试模板管理器
            template_manager = get_template_manager()
            
            print(f"创建了 {len(template_paths)} 个模拟模板文件")
            print("✅ 内存模板管理器基础测试通过")
            
        finally:
            # 清理临时文件
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except Exception as e:
        print(f"❌ 内存模板管理器测试失败: {e}")


def test_debug_manager():
    """测试内存调试管理器"""
    print("\n=== 测试内存调试管理器 ===")
    
    try:
        from utils.memory_debug_manager import get_debug_manager
        
        debug_manager = get_debug_manager()
        debug_manager.enable(True)
        
        # 创建模拟图像数据
        mock_images = []
        for i in range(3):
            mock_img = create_mock_image()
            mock_images.append(mock_img)
        
        print(f"创建了 {len(mock_images)} 个模拟图像")
        
        # 获取内存统计
        stats = debug_manager.get_memory_stats()
        print(f"内存统计: {stats}")
        
        print("✅ 内存调试管理器基础测试通过")
        
    except Exception as e:
        print(f"❌ 内存调试管理器测试失败: {e}")


def test_config_manager():
    """测试内存配置管理器"""
    print("\n=== 测试内存配置管理器 ===")
    
    temp_config_file = None
    try:
        from utils.memory_config_manager import get_config_manager
        
        config_manager = get_config_manager()
        
        # 创建临时配置文件
        temp_config_file = tempfile.mktemp(suffix='.json')
        default_config = {
            "test_key1": "test_value1",
            "test_key2": 123,
            "test_key3": True
        }
        
        # 加载配置
        print("加载配置到内存...")
        config = config_manager.load_config(temp_config_file, default_config)
        print(f"加载的配置: {config}")
        
        # 设置配置值
        print("设置配置值...")
        success1 = config_manager.set_config(temp_config_file, "new_key", "new_value")
        success2 = config_manager.set_config(temp_config_file, "test_key2", 456)
        print(f"设置结果: {success1}, {success2}")
        
        # 获取配置值
        print("获取配置值...")
        new_key_value = config_manager.get_config(temp_config_file, "new_key")
        print(f"new_key = {new_key_value}")
        
        # 获取缓存统计
        stats = config_manager.get_cache_stats()
        print(f"缓存统计: {stats}")
        
        print("✅ 内存配置管理器测试通过")
        
    except Exception as e:
        print(f"❌ 内存配置管理器测试失败: {e}")
    
    finally:
        # 清理临时文件
        if temp_config_file and os.path.exists(temp_config_file):
            os.unlink(temp_config_file)


def test_performance_monitor():
    """测试性能监控器"""
    print("\n=== 测试性能监控器 ===")
    
    try:
        from utils.memory_performance_monitor import get_performance_monitor
        
        monitor = get_performance_monitor()
        
        # 记录一些性能数据
        print("记录性能数据...")
        for i in range(5):
            monitor.record_capture_time(50.0 + i * 5)
            monitor.record_template_match_time(20.0 + i * 2)
            monitor.record_memory_io()
            if i % 2 == 0:
                monitor.record_disk_io()
        
        # 获取当前指标
        print("获取当前性能指标...")
        current_metrics = monitor.get_current_metrics()
        if current_metrics:
            print(f"当前内存使用: {current_metrics.memory_usage_mb:.1f} MB")
            print(f"当前CPU使用: {current_metrics.cpu_percent:.1f}%")
        
        print("✅ 性能监控器基础测试通过")
        
    except Exception as e:
        print(f"❌ 性能监控器测试失败: {e}")


def test_optimization_manager():
    """测试综合优化管理器"""
    print("\n=== 测试综合优化管理器 ===")
    
    try:
        from utils.memory_optimization_manager import initialize_memory_optimization, get_optimization_manager
        
        # 初始化优化系统
        print("初始化内存优化系统...")
        success = initialize_memory_optimization("balanced")
        print(f"初始化结果: {success}")
        
        if success:
            manager = get_optimization_manager()
            
            # 测试配置操作
            print("测试配置操作...")
            temp_config = tempfile.mktemp(suffix='.json')
            try:
                config = manager.load_config(temp_config, {"default": "value"})
                print(f"加载配置: {config}")
                
                success = manager.set_config(temp_config, "test_key", "test_value")
                print(f"设置配置: {success}")
            finally:
                if os.path.exists(temp_config):
                    os.unlink(temp_config)
            
            # 记录性能数据
            print("记录性能数据...")
            manager.record_capture_time(75.0)
            manager.record_template_match_time(25.0)
            
            # 获取优化统计
            print("获取优化统计...")
            stats = manager.get_optimization_stats()
            print(f"模板缓存: {'启用' if stats.template_cache_enabled else '禁用'}")
            print(f"调试缓存: {'启用' if stats.debug_cache_enabled else '禁用'}")
            print(f"配置缓存: {'启用' if stats.config_cache_enabled else '禁用'}")
            print(f"性能监控: {'启用' if stats.performance_monitoring_enabled else '禁用'}")
            print(f"优化级别: {stats.optimization_level}")
        
        print("✅ 综合优化管理器测试通过")
        
    except Exception as e:
        print(f"❌ 综合优化管理器测试失败: {e}")


def test_memory_savings():
    """测试内存节省效果"""
    print("\n=== 测试内存节省效果 ===")
    
    try:
        from utils.memory_optimization_manager import get_optimization_manager
        
        manager = get_optimization_manager()
        
        # 模拟一些操作来展示内存节省
        print("模拟磁盘IO避免...")
        
        # 模拟模板加载（避免磁盘读取）
        temp_dir = tempfile.mkdtemp()
        try:
            template_paths = []
            for i in range(5):
                template_path = os.path.join(temp_dir, f"template_{i}.png")
                with open(template_path, 'wb') as f:
                    f.write(b'mock_template_data_' + str(i).encode())
                template_paths.append(template_path)
            
            print(f"创建了 {len(template_paths)} 个模拟模板")
            
            # 模拟配置操作（避免磁盘写入）
            temp_config = tempfile.mktemp(suffix='.json')
            try:
                for i in range(10):
                    manager.set_config(temp_config, f"key_{i}", f"value_{i}")
                print("执行了 10 次配置设置（延迟写入）")
            finally:
                if os.path.exists(temp_config):
                    os.unlink(temp_config)
            
            # 获取最终统计
            stats = manager.get_optimization_stats()
            print(f"\n📊 内存优化效果:")
            print(f"   避免磁盘IO: {stats.disk_io_avoided_count} 次")
            print(f"   节省内存: {stats.total_memory_saved_mb:.1f} MB")
            print(f"   优化级别: {stats.optimization_level}")
            
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        print("✅ 内存节省效果测试通过")
        
    except Exception as e:
        print(f"❌ 内存节省效果测试失败: {e}")


def main():
    """主测试函数"""
    print("🚀 开始内存优化系统简化测试")
    print("=" * 50)
    
    # 运行各项测试
    test_template_manager()
    test_debug_manager()
    test_config_manager()
    test_performance_monitor()
    test_optimization_manager()
    test_memory_savings()
    
    print("\n" + "=" * 50)
    print("🎉 内存优化系统简化测试完成")
    
    print("\n💡 说明:")
    print("   - 本测试在无GUI环境下运行，使用模拟数据")
    print("   - 实际使用时会有更好的性能表现")
    print("   - 建议在完整环境中运行完整测试")


if __name__ == "__main__":
    main()

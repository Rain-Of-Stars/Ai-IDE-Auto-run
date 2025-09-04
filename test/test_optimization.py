# -*- coding: utf-8 -*-
"""
资源优化测试脚本
测试不同配置下的资源占用情况
"""
import os
import sys
import time
import psutil
from pathlib import Path

# 添加项目根目录到路径（兼容移动到 test/ 目录后）
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def measure_file_size(file_path):
    """测量文件大小"""
    if os.path.exists(file_path):
        size = os.path.getsize(file_path)
        return f"{size / 1024:.1f}KB"
    return "不存在"

def test_style_files():
    """测试样式文件大小"""
    print("📁 样式文件大小对比:")
    print("-" * 40)
    
    styles = {
        "极简样式": "assets/styles/minimal.qss",
        "轻量样式": "assets/styles/modern_flat_lite.qss", 
        "完整样式": "assets/styles/modern_flat.qss"
    }
    
    for name, path in styles.items():
        size = measure_file_size(path)
        print(f"   {name}: {size}")

def test_icon_cache():
    """测试图标缓存优化"""
    print("\n🎨 图标缓存测试:")
    print("-" * 40)
    
    try:
        from auto_approve.menu_icons import MenuIconManager
        
        # 测试原始缓存
        original_cache_size = getattr(MenuIconManager, '_max_cache_size', 'unlimited')
        print(f"   原始缓存限制: {original_cache_size}")
        
        # 应用优化
        MenuIconManager._max_cache_size = 5
        print(f"   优化后缓存限制: {MenuIconManager._max_cache_size}")
        
        # 创建一些图标测试缓存
        start_time = time.time()
        for i in range(10):
            icon = MenuIconManager.create_icon("test", 16, f"#FF{i:02d}{i:02d}{i:02d}")
        creation_time = (time.time() - start_time) * 1000
        
        print(f"   创建10个图标耗时: {creation_time:.1f}ms")
        print(f"   实际缓存数量: {len(MenuIconManager._icon_cache)}")
        
    except ImportError as e:
        print(f"   ⚠️ 无法导入图标管理器: {e}")

def test_performance_profiles():
    """测试性能配置档案"""
    print("\n⚙️ 性能配置档案:")
    print("-" * 40)
    
    try:
        from auto_approve.performance_config import PerformanceConfigManager
        
        config_manager = PerformanceConfigManager()
        profiles = config_manager.PROFILES
        
        for name, profile in profiles.items():
            print(f"   {profile.name} ({name}):")
            print(f"     - 状态更新间隔: {profile.status_update_interval}s")
            print(f"     - 图标缓存大小: {profile.template_cache_size}")
            print(f"     - 动画启用: {profile.animations_enabled}")
            print(f"     - 工作线程数: {profile.max_worker_threads}")
            print()
            
    except ImportError as e:
        print(f"   ⚠️ 无法导入性能配置: {e}")

def test_resource_optimizer():
    """测试资源优化器"""
    print("🔧 资源优化器测试:")
    print("-" * 40)
    
    try:
        from tools.resource_optimizer import ResourceOptimizer
        
        optimizer = ResourceOptimizer()
        
        # 分析系统资源
        system_info = optimizer.analyze_system_resources()
        print(f"   系统内存: {system_info.get('memory_total_gb', 'N/A')}GB")
        print(f"   CPU核心数: {system_info.get('cpu_count', 'N/A')}")
        print(f"   内存使用率: {system_info.get('memory_usage_percent', 'N/A')}%")
        
        # 获取推荐配置
        profile = optimizer.recommend_performance_profile()
        print(f"   推荐配置: {profile}")
        
        # 获取推荐样式
        style = optimizer.optimize_styles()
        print(f"   推荐样式: {style}")
        
        # 获取推荐缓存大小
        cache_size = optimizer.optimize_icon_cache()
        print(f"   推荐缓存: {cache_size}个")
        
    except ImportError as e:
        print(f"   ⚠️ 无法导入资源优化器: {e}")

def test_memory_usage():
    """测试内存使用情况"""
    print("\n💾 内存使用测试:")
    print("-" * 40)
    
    process = psutil.Process()
    memory_info = process.memory_info()
    
    print(f"   当前进程内存: {memory_info.rss / 1024 / 1024:.1f}MB")
    print(f"   虚拟内存: {memory_info.vms / 1024 / 1024:.1f}MB")
    
    # 系统内存
    system_memory = psutil.virtual_memory()
    print(f"   系统总内存: {system_memory.total / 1024 / 1024 / 1024:.1f}GB")
    print(f"   系统可用内存: {system_memory.available / 1024 / 1024 / 1024:.1f}GB")
    print(f"   系统内存使用率: {system_memory.percent:.1f}%")

def main():
    """主测试函数"""
    print("🧪 AI-IDE-Auto-Run 资源优化测试")
    print("=" * 50)
    
    # 测试样式文件
    test_style_files()
    
    # 测试图标缓存
    test_icon_cache()
    
    # 测试性能配置
    test_performance_profiles()
    
    # 测试资源优化器
    test_resource_optimizer()
    
    # 测试内存使用
    test_memory_usage()
    
    print("\n✅ 测试完成！")
    print("\n💡 优化建议:")
    print("   1. 使用 main_optimized.py 启动以自动应用优化")
    print("   2. 低配置设备建议使用极简模式")
    print("   3. 定期运行 tools/resource_optimizer.py 检查优化状态")

if __name__ == "__main__":
    main()

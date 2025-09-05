# -*- coding: utf-8 -*-
"""
内存优化系统测试脚本

测试内容：
1. 内存模板管理器功能测试
2. 内存调试管理器功能测试
3. 内存配置管理器功能测试
4. 性能监控器功能测试
5. 综合优化管理器测试
"""
import os
import sys
import time
import tempfile
import numpy as np
import json
from pathlib import Path

# 设置OpenCV无GUI模式
os.environ['OPENCV_IO_ENABLE_OPENEXR'] = '1'
try:
    import cv2
    # 设置无GUI后端
    cv2.setUseOptimized(True)
except ImportError:
    print("警告: OpenCV不可用，将使用模拟数据进行测试")
    cv2 = None

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.memory_template_manager import get_template_manager
from utils.memory_debug_manager import get_debug_manager
from utils.memory_config_manager import get_config_manager
from utils.memory_performance_monitor import get_performance_monitor
from utils.memory_optimization_manager import get_optimization_manager, initialize_memory_optimization


def create_test_template(width=100, height=100, color=(255, 0, 0)):
    """创建测试模板图像"""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = color
    if cv2 is not None:
        cv2.putText(img, "TEST", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    else:
        # 模拟文本绘制
        img[40:60, 10:80] = (255, 255, 255)
    return img


def test_template_manager():
    """测试内存模板管理器"""
    print("\n=== 测试内存模板管理器 ===")
    
    # 创建临时模板文件
    temp_dir = tempfile.mkdtemp()
    template_paths = []
    
    try:
        # 创建测试模板
        for i in range(3):
            template_path = os.path.join(temp_dir, f"template_{i}.png")
            test_img = create_test_template(color=(255, i*50, i*100))
            if cv2 is not None:
                cv2.imwrite(template_path, test_img)
            else:
                # 模拟保存图像文件
                with open(template_path, 'wb') as f:
                    f.write(b'fake_image_data')
            template_paths.append(template_path)
        
        # 测试模板管理器
        template_manager = get_template_manager()
        
        # 加载模板
        print("加载模板到内存...")
        loaded_count = template_manager.load_templates(template_paths)
        print(f"成功加载 {loaded_count} 个模板")
        
        # 获取模板数据
        print("从内存获取模板数据...")
        templates = template_manager.get_templates(template_paths)
        print(f"获取到 {len(templates)} 个模板数据")
        
        # 验证模板数据
        for i, (template_data, size) in enumerate(templates):
            print(f"模板 {i}: 尺寸 {template_data.shape}, 大小 {size}")
        
        # 获取缓存统计
        stats = template_manager.get_cache_stats()
        print(f"缓存统计: {stats}")
        
        print("✅ 内存模板管理器测试通过")
        
    except Exception as e:
        print(f"❌ 内存模板管理器测试失败: {e}")
    
    finally:
        # 清理临时文件
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_debug_manager():
    """测试内存调试管理器"""
    print("\n=== 测试内存调试管理器 ===")
    
    try:
        debug_manager = get_debug_manager()
        debug_manager.enable(True)
        
        # 保存测试图像
        print("保存调试图像到内存...")
        test_images = []
        for i in range(5):
            test_img = create_test_template(color=(i*50, 255, i*30))
            image_id = debug_manager.save_debug_image(
                test_img, f"test_image_{i}", "test_category"
            )
            test_images.append(image_id)
            print(f"保存图像 {i}: ID = {image_id}")
        
        # 列出调试图像
        print("列出内存中的调试图像...")
        images_info = debug_manager.list_debug_images()
        print(f"内存中有 {len(images_info)} 张调试图像")
        
        # 获取图像数据
        print("从内存获取图像数据...")
        for image_id in test_images[:2]:  # 只测试前两张
            if image_id:
                img_data = debug_manager.get_debug_image(image_id)
                if img_data is not None:
                    print(f"成功获取图像 {image_id}: {img_data.shape}")
        
        # 获取内存统计
        stats = debug_manager.get_memory_stats()
        print(f"内存统计: {stats}")
        
        # 测试导出功能
        temp_dir = tempfile.mkdtemp()
        try:
            print("测试导出功能...")
            exported_count = debug_manager.export_to_disk(temp_dir)
            print(f"导出了 {exported_count} 张图像到 {temp_dir}")
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        print("✅ 内存调试管理器测试通过")
        
    except Exception as e:
        print(f"❌ 内存调试管理器测试失败: {e}")


def test_config_manager():
    """测试内存配置管理器"""
    print("\n=== 测试内存配置管理器 ===")
    
    temp_config_file = None
    try:
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
        config_manager.set_config(temp_config_file, "new_key", "new_value")
        config_manager.set_config(temp_config_file, "test_key2", 456)
        
        # 批量更新配置
        print("批量更新配置...")
        updates = {
            "batch_key1": "batch_value1",
            "batch_key2": [1, 2, 3],
            "batch_key3": {"nested": "value"}
        }
        config_manager.update_config(temp_config_file, updates)
        
        # 获取配置值
        print("获取配置值...")
        new_key_value = config_manager.get_config(temp_config_file, "new_key")
        print(f"new_key = {new_key_value}")
        
        full_config = config_manager.get_config(temp_config_file)
        print(f"完整配置: {full_config}")
        
        # 立即保存配置
        print("保存配置到磁盘...")
        success = config_manager.save_config(temp_config_file)
        print(f"保存结果: {success}")
        
        # 验证文件是否存在
        if os.path.exists(temp_config_file):
            with open(temp_config_file, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
            print(f"磁盘上的配置: {saved_config}")
        
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
        monitor = get_performance_monitor()
        
        # 启动监控
        print("启动性能监控...")
        monitor.start_monitoring()
        
        # 记录一些性能数据
        print("记录性能数据...")
        for i in range(10):
            monitor.record_capture_time(50.0 + i * 5)
            monitor.record_template_match_time(20.0 + i * 2)
            monitor.record_memory_io()
            if i % 3 == 0:
                monitor.record_disk_io()
            time.sleep(0.1)
        
        # 等待一些监控数据
        print("等待监控数据收集...")
        time.sleep(2.0)
        
        # 获取当前指标
        print("获取当前性能指标...")
        current_metrics = monitor.get_current_metrics()
        if current_metrics:
            print(f"当前内存使用: {current_metrics.memory_usage_mb:.1f} MB")
            print(f"当前CPU使用: {current_metrics.cpu_percent:.1f}%")
            print(f"平均捕获时间: {current_metrics.capture_time_ms:.1f} ms")
        
        # 获取性能摘要
        print("获取性能摘要...")
        summary = monitor.get_performance_summary(duration_minutes=1)
        if summary:
            print(f"内存使用摘要: {summary.get('memory_usage_mb', {})}")
            print(f"IO性能: {summary.get('io_performance', {})}")
        
        # 停止监控
        print("停止性能监控...")
        monitor.stop_monitoring()
        
        print("✅ 性能监控器测试通过")
        
    except Exception as e:
        print(f"❌ 性能监控器测试失败: {e}")


def test_optimization_manager():
    """测试综合优化管理器"""
    print("\n=== 测试综合优化管理器 ===")
    
    try:
        # 初始化优化系统
        print("初始化内存优化系统...")
        success = initialize_memory_optimization("balanced")
        print(f"初始化结果: {success}")
        
        manager = get_optimization_manager()
        
        # 创建测试模板
        temp_dir = tempfile.mkdtemp()
        template_paths = []
        
        try:
            for i in range(2):
                template_path = os.path.join(temp_dir, f"opt_template_{i}.png")
                test_img = create_test_template(color=(255, i*100, i*50))
                cv2.imwrite(template_path, test_img)
                template_paths.append(template_path)
            
            # 测试模板加载
            print("测试模板加载...")
            loaded_count = manager.load_templates(template_paths)
            print(f"加载了 {loaded_count} 个模板")
            
            # 测试模板获取
            print("测试模板获取...")
            templates = manager.get_templates(template_paths)
            print(f"获取了 {len(templates)} 个模板")
            
            # 测试调试图像保存
            print("测试调试图像保存...")
            test_img = create_test_template(color=(0, 255, 255))
            image_id = manager.save_debug_image(test_img, "optimization_test", "test")
            print(f"保存调试图像: {image_id}")
            
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
            print(f"优化统计: {stats}")
            
            # 获取性能摘要
            print("获取性能摘要...")
            summary = manager.get_performance_summary()
            if summary:
                print(f"性能摘要: {summary.get('optimization', {})}")
            
            print("✅ 综合优化管理器测试通过")
            
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        
    except Exception as e:
        print(f"❌ 综合优化管理器测试失败: {e}")


def main():
    """主测试函数"""
    print("🚀 开始内存优化系统测试")
    print("=" * 50)
    
    # 运行各项测试
    test_template_manager()
    test_debug_manager()
    test_config_manager()
    test_performance_monitor()
    test_optimization_manager()
    
    print("\n" + "=" * 50)
    print("🎉 内存优化系统测试完成")
    
    # 显示最终统计
    try:
        manager = get_optimization_manager()
        final_stats = manager.get_optimization_stats()
        print(f"\n📊 最终统计:")
        print(f"   避免磁盘IO: {final_stats.disk_io_avoided_count} 次")
        print(f"   节省内存: {final_stats.total_memory_saved_mb:.1f} MB")
        print(f"   缓存命中率: {final_stats.cache_hit_rate_percent:.1f}%")
        print(f"   优化级别: {final_stats.optimization_level}")
    except Exception as e:
        print(f"获取最终统计失败: {e}")


if __name__ == "__main__":
    main()

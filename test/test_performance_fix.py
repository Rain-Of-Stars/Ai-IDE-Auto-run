# -*- coding: utf-8 -*-
"""
性能修复测试脚本

测试优化后的WGC捕获性能，验证卡顿问题是否得到解决
"""

import os
import sys
import time
import tempfile
import cv2
import numpy as np

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_approve.config_manager import load_config
from capture.capture_manager import CaptureManager


def test_capture_performance():
    """测试捕获性能"""
    print("🔍 测试WGC捕获性能...")
    
    try:
        # 加载配置
        config = load_config()
        print(f"配置加载成功:")
        print(f"  - 扫描间隔: {config.interval_ms}ms")
        print(f"  - FPS限制: {getattr(config, 'fps_max', 30)}")
        print(f"  - 模板数量: {len(getattr(config, 'template_paths', []))}")
        print(f"  - 灰度匹配: {config.grayscale}")
        
        # 创建捕获管理器
        manager = CaptureManager()
        manager.configure(
            fps=getattr(config, 'fps_max', 20),
            include_cursor=False,
            border_required=False,
            restore_minimized=True
        )
        
        # 尝试打开窗口捕获
        target_hwnd = getattr(config, 'target_hwnd', 0)
        if target_hwnd > 0:
            print(f"尝试打开窗口句柄: {target_hwnd}")
            success = manager.open_window(target_hwnd)
        else:
            target_title = getattr(config, 'target_window_title', '')
            if target_title:
                print(f"尝试打开窗口标题: {target_title}")
                success = manager.open_window(target_title, True)
            else:
                print("❌ 未配置有效的目标窗口")
                return False
        
        if not success:
            print("❌ 无法打开窗口捕获")
            return False
        
        print("✅ 窗口捕获已启动")
        
        # 测试捕获性能
        print("\n📸 开始性能测试...")
        capture_times = []
        frame_sizes = []
        
        for i in range(10):
            print(f"测试 {i+1}/10...", end=" ")
            
            start_time = time.monotonic()
            frame = manager.capture_frame()
            capture_time = (time.monotonic() - start_time) * 1000
            
            if frame is not None:
                capture_times.append(capture_time)
                frame_sizes.append(frame.nbytes)
                print(f"✅ {capture_time:.1f}ms, {frame.nbytes/1024:.1f}KB")
            else:
                print("❌ 捕获失败")
            
            time.sleep(0.2)  # 等待200ms
        
        manager.close()
        
        # 分析结果
        if capture_times:
            avg_time = sum(capture_times) / len(capture_times)
            max_time = max(capture_times)
            min_time = min(capture_times)
            avg_size = sum(frame_sizes) / len(frame_sizes)
            
            print(f"\n📊 性能统计:")
            print(f"  - 平均捕获时间: {avg_time:.1f}ms")
            print(f"  - 最大捕获时间: {max_time:.1f}ms")
            print(f"  - 最小捕获时间: {min_time:.1f}ms")
            print(f"  - 平均帧大小: {avg_size/1024:.1f}KB")
            print(f"  - 成功率: {len(capture_times)/10*100:.0f}%")
            
            # 性能评估
            if avg_time < 30:
                print("✅ 捕获性能优秀")
            elif avg_time < 50:
                print("⚠️  捕获性能一般")
            else:
                print("❌ 捕获性能较差")
                
            return avg_time < 50
        else:
            print("❌ 所有捕获测试都失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_template_matching():
    """测试模板匹配性能"""
    print("\n🖼️  测试模板匹配性能...")
    
    try:
        config = load_config()
        template_paths = getattr(config, 'template_paths', [])
        if not template_paths:
            template_paths = [config.template_path]
        
        # 创建测试图像
        test_img = np.random.randint(0, 255, (800, 600, 3), dtype=np.uint8)
        if config.grayscale:
            test_img = cv2.cvtColor(test_img, cv2.COLOR_BGR2GRAY)
        
        print(f"测试图像: {test_img.shape}")
        print(f"模板数量: {len(template_paths)}")
        
        match_times = []
        
        for i, template_path in enumerate(template_paths):
            if not os.path.exists(template_path):
                print(f"模板{i+1}: ❌ 文件不存在 - {template_path}")
                continue
            
            template = cv2.imread(template_path)
            if template is None:
                print(f"模板{i+1}: ❌ 无法加载 - {template_path}")
                continue
            
            if config.grayscale and len(template.shape) == 3:
                template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            
            print(f"模板{i+1}: {template.shape}, ", end="")
            
            # 测试匹配性能
            start_time = time.monotonic()
            result = cv2.matchTemplate(test_img, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            match_time = (time.monotonic() - start_time) * 1000
            
            match_times.append(match_time)
            print(f"{match_time:.1f}ms, 最大值: {max_val:.3f}")
        
        if match_times:
            total_time = sum(match_times)
            avg_time = total_time / len(match_times)
            
            print(f"\n📊 匹配性能统计:")
            print(f"  - 总匹配时间: {total_time:.1f}ms")
            print(f"  - 平均单模板时间: {avg_time:.1f}ms")
            print(f"  - 最慢模板时间: {max(match_times):.1f}ms")
            
            # 性能评估
            if total_time < 50:
                print("✅ 模板匹配性能优秀")
            elif total_time < 100:
                print("⚠️  模板匹配性能一般")
            else:
                print("❌ 模板匹配性能较差")
                
            return total_time < 100
        else:
            print("❌ 没有有效的模板文件")
            return False
            
    except Exception as e:
        print(f"❌ 模板匹配测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_io_performance():
    """测试IO性能"""
    print("\n💾 测试IO性能...")
    
    try:
        # 测试临时文件IO
        temp_dir = tempfile.mkdtemp(prefix='perf_test_')
        print(f"临时目录: {temp_dir}")
        
        io_times = []
        test_img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        for i in range(5):
            print(f"IO测试 {i+1}/5...", end=" ")
            
            start_time = time.monotonic()
            
            # 写入文件
            temp_file = os.path.join(temp_dir, f'test_{i}.png')
            cv2.imwrite(temp_file, test_img)
            
            # 读取文件
            img = cv2.imread(temp_file)
            
            # 删除文件
            os.unlink(temp_file)
            
            io_time = (time.monotonic() - start_time) * 1000
            io_times.append(io_time)
            print(f"{io_time:.1f}ms")
        
        # 清理临时目录
        os.rmdir(temp_dir)
        
        avg_io_time = sum(io_times) / len(io_times)
        max_io_time = max(io_times)
        
        print(f"\n📊 IO性能统计:")
        print(f"  - 平均IO时间: {avg_io_time:.1f}ms")
        print(f"  - 最大IO时间: {max_io_time:.1f}ms")
        
        # 性能评估
        if avg_io_time < 10:
            print("✅ IO性能优秀")
        elif avg_io_time < 20:
            print("⚠️  IO性能一般")
        else:
            print("❌ IO性能较差")
            
        return avg_io_time < 20
        
    except Exception as e:
        print(f"❌ IO测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("🚀 开始性能修复验证测试")
    print("="*50)
    
    results = []
    
    # 测试捕获性能
    capture_ok = test_capture_performance()
    results.append(("WGC捕获", capture_ok))
    
    # 测试模板匹配性能
    match_ok = test_template_matching()
    results.append(("模板匹配", match_ok))
    
    # 测试IO性能
    io_ok = test_io_performance()
    results.append(("IO操作", io_ok))
    
    # 总结
    print("\n" + "="*50)
    print("📋 测试结果总结")
    print("="*50)
    
    all_ok = True
    for test_name, ok in results:
        status = "✅ 通过" if ok else "❌ 失败"
        print(f"  {test_name}: {status}")
        if not ok:
            all_ok = False
    
    print("\n🎯 总体评估:")
    if all_ok:
        print("✅ 所有性能测试通过，卡顿问题应该得到改善")
    else:
        print("⚠️  部分测试未通过，可能仍存在性能问题")
    
    print("\n💡 优化建议:")
    print("  • 确保扫描间隔设置为1500ms以上")
    print("  • 启用灰度匹配模式")
    print("  • 减少模板数量到3-5个")
    print("  • 设置合适的ROI区域")
    print("  • 关闭不必要的后台程序")
    
    print("="*50)


if __name__ == "__main__":
    main()

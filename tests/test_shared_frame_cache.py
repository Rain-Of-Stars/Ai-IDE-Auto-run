# -*- coding: utf-8 -*-
"""
测试共享帧缓存系统
"""

import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_shared_frame_cache():
    """测试共享帧缓存系统"""
    try:
        from capture import CaptureManager
        import cv2
        import numpy as np
        
        print("🔍 测试共享帧缓存系统")
        print("=" * 50)
        
        # 创建捕获管理器
        manager = CaptureManager()
        print("✅ CaptureManager创建成功")
        
        # 配置参数
        manager.configure(
            fps=30,
            include_cursor=False,
            border_required=False,
            restore_minimized=True
        )
        print("✅ 参数配置完成")
        
        # 尝试打开屏幕捕获（更稳定）
        print("🎯 尝试打开屏幕捕获...")
        if not manager.open_monitor(1):
            print("❌ 无法打开屏幕捕获")
            return False
        
        print("✅ 屏幕捕获已启动")
        
        # 等待捕获稳定
        print("⏳ 等待捕获稳定...")
        time.sleep(2.0)
        
        # 测试共享帧缓存
        print("\n📊 测试共享帧缓存:")
        
        # 模拟预览窗口获取帧
        print("🖼️ 预览窗口获取帧...")
        preview_frame = manager.get_shared_frame("preview")
        if preview_frame is not None:
            h, w = preview_frame.shape[:2]
            mean_val = np.mean(preview_frame)
            print(f"  ✅ 预览帧: {w}x{h}, 平均值: {mean_val:.2f}")
            
            # 保存预览图像
            preview_filename = f"shared_preview_{int(time.time())}.png"
            cv2.imwrite(preview_filename, preview_frame)
            print(f"  💾 预览图像已保存: {preview_filename}")
        else:
            print("  ❌ 预览帧获取失败")
            return False
        
        # 模拟检测系统获取同一帧
        print("🔍 检测系统获取帧...")
        detection_frame = manager.get_shared_frame("detection")
        if detection_frame is not None:
            h, w = detection_frame.shape[:2]
            mean_val = np.mean(detection_frame)
            print(f"  ✅ 检测帧: {w}x{h}, 平均值: {mean_val:.2f}")
            
            # 验证是否是同一帧数据（内存共享）
            if np.array_equal(preview_frame, detection_frame):
                print("  ✅ 预览帧和检测帧数据一致（内存共享成功）")
            else:
                print("  ⚠️ 预览帧和检测帧数据不一致")
            
            # 保存检测图像
            detection_filename = f"shared_detection_{int(time.time())}.png"
            cv2.imwrite(detection_filename, detection_frame)
            print(f"  💾 检测图像已保存: {detection_filename}")
        else:
            print("  ❌ 检测帧获取失败")
        
        # 获取缓存统计
        print("\n📈 缓存统计信息:")
        stats = manager.get_cache_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # 模拟预览窗口关闭
        print("\n🔚 模拟预览窗口关闭...")
        manager.release_shared_frame("preview")
        
        # 检查缓存状态
        stats = manager.get_cache_stats()
        print(f"  剩余用户数: {stats['current_users']}")
        print(f"  剩余用户: {stats['users']}")
        
        # 模拟检测完成
        print("🔚 模拟检测完成...")
        manager.release_shared_frame("detection")
        
        # 最终缓存状态
        stats = manager.get_cache_stats()
        print(f"  最终用户数: {stats['current_users']}")
        print(f"  缓存命中率: {stats['hit_rate']:.1%}")
        
        # 关闭捕获
        manager.close()
        print("🔚 捕获已关闭")
        
        print("\n✅ 共享帧缓存测试完成！")
        return True
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_shared_frame_cache()

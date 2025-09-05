# -*- coding: utf-8 -*-
"""
直接测试windows_capture库和修复后的Frame处理
"""

import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_direct_wgc():
    """直接测试windows_capture库"""
    try:
        import windows_capture
        import numpy as np
        import cv2
        
        print("🔍 直接测试windows_capture库")
        print("=" * 50)
        
        # 创建捕获会话
        capture = windows_capture.WindowsCapture(
            cursor_capture=False,
            draw_border=False,
            minimum_update_interval=100,
            dirty_region=False
        )
        print("✅ WindowsCapture创建成功")
        
        frame_count = 0
        success_count = 0
        
        def frame_callback(frame, control):
            nonlocal frame_count, success_count
            frame_count += 1
            
            print(f"\n📸 处理第 {frame_count} 帧:")
            print(f"  Frame类型: {type(frame)}")
            print(f"  Frame尺寸: {frame.width}x{frame.height}")
            
            # 测试修复后的Frame处理逻辑
            try:
                # 方法1：使用convert_to_bgr()
                bgr_frame = frame.convert_to_bgr()
                if bgr_frame is not None and hasattr(bgr_frame, 'frame_buffer'):
                    buffer = bgr_frame.frame_buffer
                    if buffer is not None and isinstance(buffer, np.ndarray):
                        print(f"  BGR buffer形状: {buffer.shape}")
                        
                        if len(buffer.shape) == 3 and buffer.shape[2] == 3:
                            # 已经是BGR格式
                            bgr_result = buffer.copy()
                            mean_val = np.mean(bgr_result)
                            print(f"  ✅ BGR图像提取成功: {bgr_result.shape}")
                            print(f"  📊 平均像素值: {mean_val:.2f}")
                            
                            if mean_val > 1.0:
                                success_count += 1
                                print(f"  ✅ 图像包含有效数据")
                                
                                # 保存图像
                                filename = f"direct_wgc_test_{frame_count}_{int(time.time())}.png"
                                cv2.imwrite(filename, bgr_result)
                                print(f"  💾 图像已保存: {filename}")
                            else:
                                print(f"  ⚠️ 图像可能为全黑")
                        else:
                            print(f"  ❌ BGR buffer格式异常: {buffer.shape}")
                    else:
                        print(f"  ❌ BGR buffer无效")
                else:
                    print(f"  ❌ convert_to_bgr()失败")
                
            except Exception as e:
                print(f"  ❌ Frame处理失败: {e}")
                import traceback
                traceback.print_exc()
            
            # 测试3帧后停止
            if frame_count >= 3:
                control.stop()
        
        def closed_callback():
            print("🔚 捕获会话已关闭")
        
        # 设置回调
        capture.frame_handler = frame_callback
        capture.closed_handler = closed_callback
        
        print("▶️ 启动捕获...")
        capture.start()
        
        # 等待完成
        timeout = 15
        start_time = time.time()
        while frame_count < 3 and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        if frame_count == 0:
            print("⏰ 超时：未收到任何帧")
            return False
        
        # 评估结果
        success_rate = success_count / frame_count if frame_count > 0 else 0
        print(f"\n📊 测试结果:")
        print(f"  总帧数: {frame_count}")
        print(f"  成功帧数: {success_count}")
        print(f"  成功率: {success_rate:.1%}")
        
        if success_rate >= 0.8:
            print("✅ 直接WGC测试通过！Frame处理修复成功！")
            return True
        else:
            print("❌ 直接WGC测试失败")
            return False
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_direct_wgc()

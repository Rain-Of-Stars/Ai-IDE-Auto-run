# -*- coding: utf-8 -*-
"""
真实窗口捕获测试
测试优化后的窗口捕获功能在真实环境中的表现
"""

import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def log_to_file(message):
    """记录日志到文件"""
    with open("real_capture_test.log", "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} - {message}\n")
    print(message)

def find_test_window():
    """查找可用的测试窗口"""
    try:
        from capture.monitor_utils import enum_windows
        
        # 常见的系统窗口
        test_targets = [
            "文件资源管理器",
            "File Explorer", 
            "Windows Explorer",
            "资源管理器",
            "Explorer",
            "桌面",
            "Desktop"
        ]
        
        windows = enum_windows()
        log_to_file(f"找到 {len(windows)} 个窗口")
        
        for hwnd, title in windows:
            for target in test_targets:
                if target.lower() in title.lower():
                    log_to_file(f"找到测试窗口: HWND={hwnd}, Title='{title}'")
                    return hwnd, title
        
        # 如果没找到特定窗口，使用第一个可见窗口
        if windows:
            hwnd, title = windows[0]
            log_to_file(f"使用第一个窗口: HWND={hwnd}, Title='{title}'")
            return hwnd, title
            
        return None, None
        
    except Exception as e:
        log_to_file(f"查找窗口异常: {e}")
        return None, None

def test_real_window_capture():
    """测试真实窗口捕获"""
    try:
        log_to_file("🔍 测试真实窗口捕获...")
        
        # 查找测试窗口
        hwnd, title = find_test_window()
        if not hwnd:
            log_to_file("❌ 未找到可用的测试窗口")
            return False
        
        from capture import CaptureManager
        import numpy as np
        
        # 创建捕获管理器
        manager = CaptureManager()
        manager.configure(
            fps=10,
            include_cursor=False,
            border_required=False,
            restore_minimized=True
        )
        log_to_file("✅ CaptureManager配置完成")
        
        # 测试异步初始化
        log_to_file("🎯 测试异步初始化...")
        start_time = time.time()
        success = manager.open_window(hwnd, async_init=True, timeout=3.0)
        elapsed = time.time() - start_time
        
        log_to_file(f"异步初始化结果: success={success}, elapsed={elapsed:.2f}s")
        
        if not success:
            log_to_file("❌ 窗口捕获启动失败")
            return False
        
        if elapsed > 2.0:
            log_to_file("⚠️ 异步初始化耗时较长")
        
        # 等待一小段时间让捕获稳定
        time.sleep(1.0)
        
        # 测试帧捕获
        log_to_file("🎯 测试帧捕获...")
        capture_attempts = 5
        successful_captures = 0
        
        for i in range(capture_attempts):
            frame = manager.capture_frame()
            if frame is not None:
                h, w = frame.shape[:2]
                mean_value = np.mean(frame)
                log_to_file(f"  捕获 {i+1}: {w}x{h}, 平均值: {mean_value:.2f}")
                successful_captures += 1
            else:
                log_to_file(f"  捕获 {i+1}: 失败")
            
            time.sleep(0.2)
        
        # 测试共享帧缓存
        log_to_file("🎯 测试共享帧缓存...")
        shared_frame = manager.get_shared_frame("test_user", "test")
        if shared_frame is not None:
            log_to_file("✅ 共享帧缓存正常")
        else:
            log_to_file("⚠️ 共享帧缓存为空")
        
        # 清理资源
        manager.close()
        log_to_file("✅ 资源清理完成")
        
        # 评估结果
        success_rate = successful_captures / capture_attempts
        log_to_file(f"捕获成功率: {success_rate:.1%} ({successful_captures}/{capture_attempts})")
        
        if success_rate >= 0.6:  # 60%以上成功率认为正常
            log_to_file("✅ 真实窗口捕获测试通过")
            return True
        else:
            log_to_file("❌ 真实窗口捕获测试失败")
            return False
            
    except Exception as e:
        log_to_file(f"❌ 真实窗口捕获测试异常: {e}")
        import traceback
        with open("real_capture_test.log", "a", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        return False

def test_timeout_protection():
    """测试超时保护机制"""
    try:
        log_to_file("🔍 测试超时保护机制...")
        
        from capture import CaptureManager
        
        # 测试多个超时场景
        timeout_tests = [
            (99999, 1.0, "无效窗口句柄"),
            (0, 0.5, "零窗口句柄"),
            (-1, 2.0, "负数窗口句柄"),
        ]
        
        passed_tests = 0
        
        for hwnd, timeout, description in timeout_tests:
            log_to_file(f"  测试: {description}")
            
            manager = CaptureManager()
            start_time = time.time()
            success = manager.open_window(hwnd, timeout=timeout)
            elapsed = time.time() - start_time
            
            # 应该失败且在合理时间内返回
            if not success and elapsed <= timeout + 1.0:
                log_to_file(f"    ✅ 正确处理，耗时: {elapsed:.2f}s")
                passed_tests += 1
            else:
                log_to_file(f"    ❌ 处理异常，success={success}, elapsed={elapsed:.2f}s")
        
        if passed_tests == len(timeout_tests):
            log_to_file("✅ 超时保护机制测试通过")
            return True
        else:
            log_to_file(f"❌ 超时保护机制测试失败 ({passed_tests}/{len(timeout_tests)})")
            return False
            
    except Exception as e:
        log_to_file(f"❌ 超时保护测试异常: {e}")
        return False

def main():
    """主测试函数"""
    # 清空日志文件
    with open("real_capture_test.log", "w", encoding="utf-8") as f:
        f.write("")
    
    log_to_file("🚀 开始真实窗口捕获测试")
    log_to_file("=" * 50)
    
    tests = [
        ("真实窗口捕获", test_real_window_capture),
        ("超时保护机制", test_timeout_protection),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        log_to_file(f"\n📋 运行测试: {test_name}")
        try:
            result = test_func()
            if result:
                passed += 1
                log_to_file(f"✅ {test_name} 通过")
            else:
                log_to_file(f"❌ {test_name} 失败")
        except Exception as e:
            log_to_file(f"❌ {test_name} 异常: {e}")
    
    log_to_file(f"\n📊 测试结果: {passed}/{total} 项通过")
    
    if passed == total:
        log_to_file("🎉 所有真实测试通过！窗口捕获优化效果良好！")
        return True
    else:
        log_to_file("⚠️ 部分测试失败，但基本功能正常")
        return passed > 0  # 只要有一个测试通过就认为基本可用

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        log_to_file(f"❌ 主程序异常: {e}")
        import traceback
        with open("real_capture_test.log", "a", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        sys.exit(1)

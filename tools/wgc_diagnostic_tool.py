# -*- coding: utf-8 -*-
"""
WGC问题诊断和修复工具

全面诊断WGC相关问题并提供自动修复方案：
1. 检查WGC库可用性
2. 验证窗口句柄有效性
3. 测试WGC捕获功能
4. 自动修复配置问题
"""

import sys
import os
import traceback

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from auto_approve.config_manager import load_config
from auto_approve.logger_manager import get_logger
from capture import CaptureManager
from tools.fix_wgc_hwnd import fix_wgc_hwnd, is_hwnd_valid, get_window_title

def check_wgc_library():
    """检查WGC库可用性"""
    print("\n=== 1. 检查WGC库可用性 ===")
    
    try:
        import windows_capture
        print("✅ windows_capture 库导入成功")
        
        if hasattr(windows_capture, 'WindowsCapture'):
            print("✅ WindowsCapture 类存在")
            return True
        else:
            print("❌ WindowsCapture 类不存在")
            return False
            
    except ImportError as e:
        print(f"❌ windows_capture 库导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ WGC库检查失败: {e}")
        return False

def check_config_validity():
    """检查配置文件有效性"""
    print("\n=== 2. 检查配置文件有效性 ===")
    
    try:
        cfg = load_config()
        target_hwnd = getattr(cfg, 'target_hwnd', 0)
        target_title = getattr(cfg, 'target_window_title', '')
        target_process = getattr(cfg, 'target_process', '')
        capture_backend = getattr(cfg, 'capture_backend', 'screen')
        
        print(f"捕获后端: {capture_backend}")
        print(f"目标HWND: {target_hwnd}")
        print(f"目标窗口标题: '{target_title}'")
        print(f"目标进程: '{target_process}'")
        
        # 检查HWND有效性
        if target_hwnd > 0:
            if is_hwnd_valid(target_hwnd):
                title = get_window_title(target_hwnd)
                print(f"✅ HWND {target_hwnd} 有效，窗口标题: '{title}'")
                return True
            else:
                print(f"❌ HWND {target_hwnd} 无效")
                return False
        else:
            print("⚠️  未配置HWND，将依赖窗口标题或进程名查找")
            return True
            
    except Exception as e:
        print(f"❌ 配置检查失败: {e}")
        return False

def test_wgc_capture():
    """测试WGC捕获功能"""
    print("\n=== 3. 测试WGC捕获功能 ===")
    
    try:
        cfg = load_config()
        manager = CaptureManager()
        
        # 配置参数
        manager.configure(
            fps=getattr(cfg, 'fps_max', 30),
            include_cursor=getattr(cfg, 'include_cursor', False),
            # 诊断工具按窗口捕获测试
            border_required=bool(getattr(cfg, 'window_border_required', getattr(cfg, 'border_required', False))),
            restore_minimized=getattr(cfg, 'restore_minimized_noactivate', True)
        )
        
        # 尝试打开窗口捕获
        target_hwnd = getattr(cfg, 'target_hwnd', 0)
        if target_hwnd > 0:
            success = manager.open_window(target_hwnd)
        else:
            target_title = getattr(cfg, 'target_window_title', '')
            if target_title:
                partial_match = getattr(cfg, 'window_title_partial_match', True)
                success = manager.open_window(target_title, partial_match)
            else:
                print("❌ 未配置有效的目标窗口")
                return False
        
        if not success:
            print("❌ WGC窗口捕获启动失败")
            return False
        
        print("✅ WGC窗口捕获启动成功")
        
        # 测试捕获一帧
        frame = manager.capture_frame()
        if frame is not None:
            h, w = frame.shape[:2]
            print(f"✅ 成功捕获帧: {w}x{h}")
            manager.close()
            return True
        else:
            print("❌ 捕获帧失败")
            manager.close()
            return False
            
    except Exception as e:
        print(f"❌ WGC捕获测试失败: {e}")
        traceback.print_exc()
        return False

def run_diagnostic():
    """运行完整诊断"""
    print("🔍 WGC问题诊断工具")
    print("=" * 50)
    
    # 1. 检查WGC库
    wgc_lib_ok = check_wgc_library()
    if not wgc_lib_ok:
        print("\n❌ WGC库不可用，请安装 windows-capture-python")
        return False
    
    # 2. 检查配置
    config_ok = check_config_validity()
    
    # 3. 如果配置有问题，尝试自动修复
    if not config_ok:
        print("\n🔧 尝试自动修复配置...")
        fix_success = fix_wgc_hwnd()
        if fix_success:
            print("✅ 配置修复成功")
            config_ok = True
        else:
            print("❌ 配置修复失败")
            return False
    
    # 4. 测试WGC捕获
    capture_ok = test_wgc_capture()
    
    # 总结
    print("\n" + "=" * 50)
    print("📋 诊断结果总结:")
    print(f"  WGC库可用性: {'✅' if wgc_lib_ok else '❌'}")
    print(f"  配置文件有效性: {'✅' if config_ok else '❌'}")
    print(f"  WGC捕获功能: {'✅' if capture_ok else '❌'}")
    
    if wgc_lib_ok and config_ok and capture_ok:
        print("\n🎉 WGC功能完全正常！")
        return True
    else:
        print("\n⚠️  存在问题需要手动处理")
        return False

def main():
    """主函数"""
    try:
        success = run_diagnostic()
        return 0 if success else 1
    except Exception as e:
        print(f"\n💥 诊断工具运行失败: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

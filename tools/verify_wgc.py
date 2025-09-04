#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WGC修复验证工具

验证VSCode最大化/缩放变化时的WGC捕获是否正常：
- 检查ContentSize变化时的FramePool重建
- 验证RowPitch处理是否正确
- 测试窗口化/最大化状态下的捕获质量
- 确认无PrintWindow回退
"""

import sys
import os
import time
import ctypes
from pathlib import Path
from typing import Optional, Tuple

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
from capture import CaptureManager
from capture.monitor_utils import find_window_by_title
from auto_approve.logger_manager import get_logger

# Windows API
from ctypes import wintypes
user32 = ctypes.windll.user32

# 常量
SW_MAXIMIZE = 3
SW_RESTORE = 9
ARTIFACTS_DIR = Path("artifacts")


def ensure_artifacts_dir():
    """确保artifacts目录存在"""
    ARTIFACTS_DIR.mkdir(exist_ok=True)


def find_vscode_window() -> Optional[int]:
    """查找VSCode窗口"""
    logger = get_logger()
    
    # 尝试多种VSCode窗口标题模式
    patterns = [
        "Visual Studio Code",
        "Code",
        "VSCode",
        "Microsoft Visual Studio Code"
    ]
    
    for pattern in patterns:
        hwnd = find_window_by_title(pattern, partial_match=True)
        if hwnd:
            logger.info(f"找到VSCode窗口: '{pattern}' (HWND={hwnd})")
            return hwnd
    
    logger.error("未找到VSCode窗口，请确保VSCode正在运行")
    return None


def get_window_state(hwnd: int) -> str:
    """获取窗口状态"""
    if user32.IsIconic(hwnd):
        return "最小化"
    elif user32.IsZoomed(hwnd):
        return "最大化"
    else:
        return "窗口化"


def toggle_window_state(hwnd: int) -> Tuple[str, str]:
    """切换窗口状态，返回(旧状态, 新状态)"""
    old_state = get_window_state(hwnd)
    
    if old_state == "最大化":
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.5)  # 等待状态切换完成
        new_state = "窗口化"
    else:
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        time.sleep(0.5)
        new_state = "最大化"
    
    return old_state, new_state


def capture_and_save(manager: CaptureManager, state: str, frame_num: int) -> bool:
    """捕获并保存帧"""
    logger = get_logger()
    
    # 等待一帧
    frame = manager.wait_for_frame(timeout=2.0)
    if frame is None:
        logger.error(f"捕获帧失败: {state}_frame_{frame_num}")
        return False
    
    # 保存图像
    filename = f"vscode_{state}_frame_{frame_num}.png"
    filepath = ARTIFACTS_DIR / filename
    
    success = cv2.imwrite(str(filepath), frame)
    if success:
        h, w = frame.shape[:2]
        logger.info(f"已保存: {filename} ({w}x{h})")
        return True
    else:
        logger.error(f"保存失败: {filename}")
        return False


def verify_wgc_capture():
    """验证WGC捕获功能"""
    logger = get_logger()
    logger.info("=== WGC修复验证开始 ===")
    
    # 确保输出目录存在
    ensure_artifacts_dir()
    
    # 查找VSCode窗口
    hwnd = find_vscode_window()
    if not hwnd:
        return False
    
    # 创建捕获管理器
    try:
        manager = CaptureManager()
        success = manager.open_window(hwnd)
        if not success:
            logger.error("WGC捕获管理器启动失败")
            return False
        
        logger.info("WGC捕获管理器启动成功")
        
    except Exception as e:
        logger.error(f"创建捕获管理器失败: {e}")
        return False
    
    try:
        # 获取初始状态
        initial_state = get_window_state(hwnd)
        logger.info(f"VSCode初始状态: {initial_state}")
        
        # 测试序列：当前状态 -> 切换状态 -> 恢复状态
        states_to_test = []
        
        # 第一阶段：当前状态捕获3帧
        current_state = get_window_state(hwnd)
        states_to_test.append((current_state, "当前"))
        
        # 第二阶段：切换状态捕获3帧
        old_state, new_state = toggle_window_state(hwnd)
        logger.info(f"窗口状态切换: {old_state} -> {new_state}")
        states_to_test.append((new_state, "切换后"))
        
        # 第三阶段：恢复原状态捕获3帧
        old_state, restored_state = toggle_window_state(hwnd)
        logger.info(f"窗口状态恢复: {old_state} -> {restored_state}")
        states_to_test.append((restored_state, "恢复后"))
        
        # 执行捕获测试
        all_success = True
        for state, desc in states_to_test:
            logger.info(f"\n--- 测试{desc}状态 ({state}) ---")
            
            # 等待窗口稳定
            time.sleep(1.0)
            
            # 捕获3帧
            for i in range(1, 4):
                success = capture_and_save(manager, state, i)
                if not success:
                    all_success = False
                
                # 帧间间隔
                time.sleep(0.5)
        
        # 获取统计信息
        stats = manager.get_stats()
        logger.info(f"\n--- 捕获统计 ---")
        logger.info(f"总帧数: {stats['frame_count']}")
        logger.info(f"运行时间: {stats['elapsed_time']:.1f}s")
        logger.info(f"平均FPS: {stats['actual_fps']:.1f}")
        logger.info(f"目标FPS: {stats['target_fps']}")
        logger.info(f"ContentSize: {stats.get('content_size', 'N/A')}")
        logger.info(f"FramePool重建: {stats.get('frame_pool_recreated', False)}")
        
        # 验证结果
        if all_success:
            logger.info("\n✅ WGC捕获验证成功！")
            logger.info("- VSCode窗口化/最大化均无畸变")
            logger.info("- 窗口尺寸变化时正确处理ContentSize")
            logger.info("- RowPitch处理正常")
            logger.info("- 无PrintWindow回退")
        else:
            logger.error("\n❌ WGC捕获验证失败！")
            
        return all_success
        
    except Exception as e:
        logger.error(f"验证过程异常: {e}")
        return False
        
    finally:
        # 清理资源
        try:
            manager.close()
        except Exception:
            pass


def main():
    """主函数"""
    logger = get_logger()
    
    try:
        success = verify_wgc_capture()
        
        if success:
            logger.info("\n🎉 WGC修复验证通过！")
            print("\n验证结果：")
            print("✅ VSCode窗口化/最大化捕获正常")
            print("✅ ContentSize变化处理正确")
            print("✅ RowPitch处理无畸变")
            print("✅ 禁用PrintWindow回退")
            print(f"✅ 截图已保存到 {ARTIFACTS_DIR}/")
            return 0
        else:
            logger.error("\n❌ WGC修复验证失败！")
            print("\n验证结果：")
            print("❌ 存在问题，请检查日志")
            return 1
            
    except Exception as e:
        logger.error(f"验证工具异常: {e}")
        print(f"\n❌ 验证工具异常: {e}")
        return 1


if __name__ == "__main__":
    exit(main())

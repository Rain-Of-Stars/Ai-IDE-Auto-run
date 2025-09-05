# -*- coding: utf-8 -*-
"""
修复扫描进程卡住问题的快速脚本
"""
import os
import sys
import time
import psutil
import multiprocessing as mp

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def kill_existing_processes():
    """杀死可能存在的僵尸进程"""
    print("🔍 检查并清理可能的僵尸进程...")
    
    killed_count = 0
    current_pid = os.getpid()
    
    try:
        # 查找所有Python进程
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    if proc.info['pid'] != current_pid:
                        cmdline = proc.info['cmdline'] or []
                        # 检查是否是我们的扫描进程
                        if any('scanner' in arg.lower() for arg in cmdline):
                            print(f"   发现可疑进程: PID={proc.info['pid']}")
                            proc.terminate()
                            killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        if killed_count > 0:
            print(f"   ✅ 清理了 {killed_count} 个可疑进程")
            time.sleep(2)  # 等待进程完全退出
        else:
            print("   ✅ 未发现可疑进程")
            
    except Exception as e:
        print(f"   ⚠️ 清理进程时出错: {e}")


def reset_multiprocessing():
    """重置多进程环境"""
    print("🔧 重置多进程环境...")
    
    try:
        # 强制设置spawn方式
        if sys.platform.startswith('win'):
            mp.set_start_method('spawn', force=True)
            print("   ✅ 设置多进程启动方式为spawn")
        
        # 测试基础多进程功能
        def test_worker(q):
            q.put("test_ok")
        
        test_queue = mp.Queue()
        test_process = mp.Process(target=test_worker, args=(test_queue,))
        
        start_time = time.time()
        test_process.start()
        
        # 等待结果
        try:
            result = test_queue.get(timeout=5)
            test_process.join(timeout=2)
            elapsed = time.time() - start_time
            print(f"   ✅ 多进程功能正常 (耗时: {elapsed:.3f}秒)")
            return True
        except:
            test_process.terminate()
            test_process.join(timeout=1)
            print("   ❌ 多进程功能异常")
            return False
            
    except Exception as e:
        print(f"   ❌ 重置多进程环境失败: {e}")
        return False


def check_system_resources():
    """检查系统资源"""
    print("📊 检查系统资源...")
    
    try:
        # 内存检查
        memory = psutil.virtual_memory()
        print(f"   内存使用率: {memory.percent:.1f}%")
        
        if memory.percent > 90:
            print("   ⚠️ 内存使用率过高，可能影响进程创建")
            return False
        
        # CPU检查
        cpu_percent = psutil.cpu_percent(interval=1)
        print(f"   CPU使用率: {cpu_percent:.1f}%")
        
        if cpu_percent > 90:
            print("   ⚠️ CPU使用率过高，可能影响进程创建")
            return False
        
        # 磁盘检查
        disk = psutil.disk_usage('.')
        print(f"   磁盘使用率: {disk.percent:.1f}%")
        
        if disk.percent > 95:
            print("   ⚠️ 磁盘空间不足，可能影响进程创建")
            return False
        
        print("   ✅ 系统资源正常")
        return True
        
    except Exception as e:
        print(f"   ❌ 检查系统资源失败: {e}")
        return False


def test_capture_manager():
    """测试捕获管理器"""
    print("🎥 测试捕获管理器...")
    
    try:
        from capture.capture_manager import CaptureManager
        
        # 创建捕获管理器
        start_time = time.time()
        capture_manager = CaptureManager()
        create_time = time.time() - start_time
        
        print(f"   捕获管理器创建耗时: {create_time:.3f}秒")
        
        if create_time > 5.0:
            print("   ⚠️ 捕获管理器创建耗时过长")
            
        # 配置捕获管理器
        capture_manager.configure(fps=30, include_cursor=False, border_required=False)
        
        # 清理
        capture_manager.close()
        
        print("   ✅ 捕获管理器测试通过")
        return True
        
    except Exception as e:
        print(f"   ❌ 捕获管理器测试失败: {e}")
        import traceback
        print(f"   详细错误: {traceback.format_exc()}")
        return False


def apply_quick_fixes():
    """应用快速修复"""
    print("🚀 应用快速修复...")
    
    fixes_applied = []
    
    try:
        # 1. 设置环境变量
        os.environ['PYTHONUNBUFFERED'] = '1'
        os.environ['QT_LOGGING_RULES'] = 'qt.qpa.window=false'
        fixes_applied.append("设置环境变量")
        
        # 2. 增加进程启动超时
        if hasattr(mp, '_default_timeout'):
            mp._default_timeout = 30  # 30秒超时
            fixes_applied.append("增加进程启动超时")
        
        # 3. 清理临时文件
        import tempfile
        temp_dir = tempfile.gettempdir()
        temp_files_cleaned = 0
        
        for filename in os.listdir(temp_dir):
            if 'python' in filename.lower() and 'mp-' in filename:
                try:
                    os.remove(os.path.join(temp_dir, filename))
                    temp_files_cleaned += 1
                except:
                    pass
        
        if temp_files_cleaned > 0:
            fixes_applied.append(f"清理了{temp_files_cleaned}个临时文件")
        
        print(f"   ✅ 应用了 {len(fixes_applied)} 个修复:")
        for fix in fixes_applied:
            print(f"     - {fix}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 应用快速修复失败: {e}")
        return False


def main():
    """主修复函数"""
    print("🔧 扫描进程卡住问题修复工具")
    print("=" * 50)
    
    # 执行修复步骤
    steps = [
        ("清理僵尸进程", kill_existing_processes),
        ("检查系统资源", check_system_resources),
        ("重置多进程环境", reset_multiprocessing),
        ("测试捕获管理器", test_capture_manager),
        ("应用快速修复", apply_quick_fixes),
    ]
    
    success_count = 0
    for step_name, step_func in steps:
        print(f"\n{step_name}...")
        try:
            if step_func():
                success_count += 1
            else:
                print(f"   ⚠️ {step_name}未完全成功")
        except Exception as e:
            print(f"   ❌ {step_name}执行异常: {e}")
    
    # 显示结果
    print("\n" + "=" * 50)
    print("📊 修复结果:")
    print("=" * 50)
    print(f"成功执行: {success_count}/{len(steps)} 个步骤")
    
    if success_count >= len(steps) - 1:
        print("\n🎉 修复完成！建议:")
        print("1. 重启应用程序")
        print("2. 尝试重新启动扫描")
        print("3. 如果问题仍然存在，请重启计算机")
    else:
        print("\n⚠️ 修复不完整，建议:")
        print("1. 以管理员权限运行此修复工具")
        print("2. 关闭防病毒软件后重试")
        print("3. 重启计算机后再次尝试")
        print("4. 检查Windows事件日志获取更多信息")
    
    print("\n💡 如果问题持续存在，可能的原因:")
    print("- Windows Defender或其他安全软件阻止进程创建")
    print("- 系统权限不足")
    print("- Python环境损坏")
    print("- 硬件资源不足")


if __name__ == "__main__":
    main()
    input("\n按回车键退出...")

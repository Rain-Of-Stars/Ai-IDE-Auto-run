# -*- coding: utf-8 -*-
"""
简单的进程测试
"""

import sys
import os
import time
import multiprocessing as mp

# 确保Windows平台使用spawn方式启动进程
if sys.platform.startswith('win'):
    mp.set_start_method('spawn', force=True)

def simple_worker(queue_in, queue_out):
    """简单的工作进程"""
    print("工作进程启动")
    count = 0
    
    while True:
        try:
            # 检查是否有命令
            try:
                command = queue_in.get(timeout=0.1)
                if command == 'stop':
                    print("工作进程收到停止命令")
                    break
            except:
                pass
            
            # 发送状态
            count += 1
            queue_out.put(f"工作进程运行中，计数: {count}")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"工作进程异常: {e}")
            break
    
    print("工作进程退出")

def main():
    """主函数"""
    print("开始简单进程测试...")
    
    # 创建队列
    queue_in = mp.Queue()
    queue_out = mp.Queue()
    
    # 创建进程
    process = mp.Process(target=simple_worker, args=(queue_in, queue_out))
    
    try:
        # 启动进程
        print("启动工作进程...")
        process.start()
        print(f"工作进程已启动，PID: {process.pid}")
        
        # 运行5秒
        start_time = time.time()
        while time.time() - start_time < 5:
            try:
                # 读取状态
                status = queue_out.get(timeout=0.1)
                print(f"收到状态: {status}")
            except:
                pass
            
            time.sleep(0.1)
        
        # 停止进程
        print("发送停止命令...")
        queue_in.put('stop')
        
        # 等待进程结束
        process.join(timeout=3)
        
        if process.is_alive():
            print("强制终止进程...")
            process.terminate()
            process.join(timeout=1)
        
        print("测试完成")
        
    except Exception as e:
        print(f"测试异常: {e}")
        if process.is_alive():
            process.terminate()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
系统状态检查测试
用于快速诊断AI-IDE-Auto-Run系统的卡顿问题
"""

import os
import sys
import time
import json
import psutil
import threading
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_system_resources():
    """检查系统资源状态"""
    print("🔍 系统资源检查")
    print("-" * 40)
    
    # CPU信息
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    cpu_percent = psutil.cpu_percent(interval=1)
    
    print(f"CPU核心数: {cpu_count}")
    if cpu_freq:
        print(f"CPU频率: {cpu_freq.current:.0f} MHz")
    print(f"CPU使用率: {cpu_percent:.1f}%")
    
    # 内存信息
    memory = psutil.virtual_memory()
    print(f"内存总量: {memory.total / 1024**3:.1f} GB")
    print(f"内存使用率: {memory.percent:.1f}%")
    print(f"可用内存: {memory.available / 1024**3:.1f} GB")
    
    # 磁盘信息
    disk = psutil.disk_usage('.')
    print(f"磁盘使用率: {disk.percent:.1f}%")
    print(f"磁盘可用空间: {disk.free / 1024**3:.1f} GB")
    
    # 问题检测
    issues = []
    if cpu_percent > 80:
        issues.append(f"CPU使用率过高: {cpu_percent:.1f}%")
    if memory.percent > 85:
        issues.append(f"内存使用率过高: {memory.percent:.1f}%")
    if disk.free < 1024**3:  # 小于1GB
        issues.append(f"磁盘空间不足: {disk.free/1024**3:.1f}GB")
    
    if issues:
        print("\n⚠️ 发现的问题:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n✅ 系统资源状态正常")
    
    return issues

def check_python_processes():
    """检查Python进程"""
    print("\n🐍 Python进程检查")
    print("-" * 40)
    
    python_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'cmdline']):
        try:
            if 'python' in proc.info['name'].lower():
                cpu = proc.cpu_percent()
                memory_mb = proc.memory_info().rss / 1024**2
                cmdline = ' '.join(proc.cmdline()[:3]) if proc.cmdline() else 'N/A'
                
                python_processes.append({
                    'pid': proc.pid,
                    'cpu': cpu,
                    'memory_mb': memory_mb,
                    'cmdline': cmdline
                })
                
                print(f"PID {proc.pid}: CPU {cpu:.1f}% | 内存 {memory_mb:.1f}MB")
                print(f"  命令行: {cmdline}")
                
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    print(f"\nPython进程总数: {len(python_processes)}")
    
    # 检查是否有高资源占用的Python进程
    high_cpu_procs = [p for p in python_processes if p['cpu'] > 50]
    high_mem_procs = [p for p in python_processes if p['memory_mb'] > 500]
    
    issues = []
    if high_cpu_procs:
        issues.append(f"发现{len(high_cpu_procs)}个高CPU占用的Python进程")
    if high_mem_procs:
        issues.append(f"发现{len(high_mem_procs)}个高内存占用的Python进程")
    
    if issues:
        print("\n⚠️ 发现的问题:")
        for issue in issues:
            print(f"  - {issue}")
    
    return python_processes, issues

def check_config_file():
    """检查配置文件"""
    print("\n⚙️ 配置文件检查")
    print("-" * 40)
    
    config_path = "config.json"
    if not os.path.exists(config_path):
        print("❌ 配置文件不存在")
        return {}, ["配置文件不存在"]
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print("✅ 配置文件加载成功")
        
        # 显示关键配置
        key_configs = {
            'interval_ms': config.get('interval_ms', 1500),
            'fps_max': config.get('fps_max', 30),
            'template_count': len(config.get('template_paths', [])),
            'debug_mode': config.get('debug_mode', False),
            'save_debug_images': config.get('save_debug_images', False),
            'grayscale': config.get('grayscale', True),
            'auto_start_scan': config.get('auto_start_scan', False)
        }
        
        print("关键配置:")
        for key, value in key_configs.items():
            print(f"  {key}: {value}")
        
        # 问题检测
        issues = []
        recommendations = []
        
        if key_configs['interval_ms'] < 1000:
            issues.append(f"扫描间隔过短: {key_configs['interval_ms']}ms")
            recommendations.append("增加扫描间隔到1500ms以上")
        
        if key_configs['fps_max'] > 10:
            issues.append(f"FPS设置过高: {key_configs['fps_max']}")
            recommendations.append("降低FPS到5以下")
        
        if key_configs['template_count'] > 3:
            issues.append(f"模板数量过多: {key_configs['template_count']}个")
            recommendations.append("减少模板数量到2-3个")
        
        if key_configs['debug_mode'] or key_configs['save_debug_images']:
            issues.append("调试功能已启用")
            recommendations.append("关闭调试模式和调试图像保存")
        
        if issues:
            print("\n⚠️ 配置问题:")
            for issue in issues:
                print(f"  - {issue}")
            
            print("\n💡 优化建议:")
            for rec in recommendations:
                print(f"  - {rec}")
        else:
            print("\n✅ 配置设置合理")
        
        return config, issues
        
    except Exception as e:
        print(f"❌ 配置文件读取失败: {e}")
        return {}, [f"配置文件读取失败: {e}"]

def check_template_files(config):
    """检查模板文件"""
    print("\n🖼️ 模板文件检查")
    print("-" * 40)
    
    template_paths = config.get('template_paths', [])
    if not template_paths:
        template_path = config.get('template_path', '')
        if template_path:
            template_paths = [template_path]
    
    if not template_paths:
        print("❌ 未配置模板文件")
        return ["未配置模板文件"]
    
    issues = []
    total_size = 0
    
    for i, path in enumerate(template_paths, 1):
        print(f"模板{i}: {path}")
        
        if not os.path.exists(path):
            issues.append(f"模板{i}文件不存在: {path}")
            print(f"  ❌ 文件不存在")
            continue
        
        try:
            file_size = os.path.getsize(path)
            total_size += file_size
            print(f"  ✅ 文件大小: {file_size / 1024:.1f} KB")
            
            # 检查文件大小
            if file_size > 1024 * 1024:  # 大于1MB
                issues.append(f"模板{i}文件过大: {file_size/1024/1024:.1f}MB")
            
        except Exception as e:
            issues.append(f"模板{i}文件检查失败: {e}")
            print(f"  ❌ 检查失败: {e}")
    
    print(f"\n模板文件总大小: {total_size / 1024:.1f} KB")
    
    if total_size > 5 * 1024 * 1024:  # 大于5MB
        issues.append(f"模板文件总大小过大: {total_size/1024/1024:.1f}MB")
    
    if issues:
        print("\n⚠️ 模板文件问题:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n✅ 模板文件状态正常")
    
    return issues

def generate_optimization_suggestions(all_issues):
    """生成优化建议"""
    print("\n🔧 系统卡顿解决方案")
    print("=" * 50)
    
    if not any(all_issues.values()):
        print("✅ 系统状态良好，未发现明显问题")
        print("\n如果仍然卡顿，建议:")
        print("  1. 重启应用程序")
        print("  2. 重启计算机")
        print("  3. 检查Windows更新")
        return
    
    print("⚠️ 发现以下问题需要解决:")
    
    issue_count = 0
    for category, issues in all_issues.items():
        if issues:
            print(f"\n{category}:")
            for issue in issues:
                issue_count += 1
                print(f"  {issue_count}. {issue}")
    
    print(f"\n💡 针对性解决方案:")
    
    # 系统资源问题
    if all_issues.get('system', []):
        print("  🖥️ 系统资源优化:")
        print("    - 关闭不必要的后台程序")
        print("    - 清理系统垃圾文件")
        print("    - 重启计算机释放资源")
    
    # 配置问题
    if all_issues.get('config', []):
        print("  ⚙️ 配置优化:")
        print("    - 增加扫描间隔到2000ms以上")
        print("    - 降低FPS到1-3之间")
        print("    - 关闭调试模式")
        print("    - 减少模板数量")
    
    # Python进程问题
    if all_issues.get('processes', []):
        print("  🐍 进程优化:")
        print("    - 关闭其他Python程序")
        print("    - 重启AI-IDE-Auto-Run应用")
        print("    - 检查是否有死循环或内存泄漏")
    
    # 模板文件问题
    if all_issues.get('templates', []):
        print("  🖼️ 模板优化:")
        print("    - 压缩模板图像文件")
        print("    - 减少模板数量到1-2个")
        print("    - 确保模板文件路径正确")
    
    print(f"\n🚀 快速修复步骤:")
    print("  1. 立即重启AI-IDE-Auto-Run应用")
    print("  2. 修改config.json: interval_ms改为2000, fps_max改为1")
    print("  3. 关闭其他占用资源的程序")
    print("  4. 如果问题持续，重启计算机")

def main():
    """主函数"""
    print("🔍 AI-IDE-Auto-Run 系统卡顿诊断")
    print("=" * 50)
    print(f"诊断时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_issues = {}
    
    # 检查系统资源
    all_issues['system'] = check_system_resources()
    
    # 检查Python进程
    processes, proc_issues = check_python_processes()
    all_issues['processes'] = proc_issues
    
    # 检查配置文件
    config, config_issues = check_config_file()
    all_issues['config'] = config_issues
    
    # 检查模板文件
    if config:
        all_issues['templates'] = check_template_files(config)
    else:
        all_issues['templates'] = []
    
    # 生成优化建议
    generate_optimization_suggestions(all_issues)
    
    print("\n" + "=" * 50)
    print("诊断完成！")

if __name__ == "__main__":
    main()

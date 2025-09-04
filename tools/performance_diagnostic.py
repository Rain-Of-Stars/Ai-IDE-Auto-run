# -*- coding: utf-8 -*-
"""
性能诊断工具 - 诊断和解决卡顿问题

用于分析和解决"开始捕获后变得异常卡顿"的问题：
1. 检查WGC捕获性能
2. 分析模板匹配开销
3. 监控内存和CPU使用
4. 提供优化建议
"""

import os
import sys
import time
import tempfile
import shutil
from typing import List, Dict, Any
import psutil
import cv2
import numpy as np

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import load_config
from capture.capture_manager import CaptureManager
from tools.performance_monitor import get_performance_monitor, print_performance_report


class PerformanceDiagnostic:
    """性能诊断器"""
    
    def __init__(self):
        self.config = load_config()
        self.issues = []
        self.recommendations = []
        
    def run_full_diagnostic(self) -> Dict[str, Any]:
        """运行完整的性能诊断"""
        print("🔍 开始性能诊断...")
        print("="*60)
        
        results = {
            "system_info": self._check_system_resources(),
            "config_analysis": self._analyze_config(),
            "capture_test": self._test_capture_performance(),
            "template_analysis": self._analyze_templates(),
            "io_performance": self._test_io_performance(),
            "issues": self.issues,
            "recommendations": self.recommendations
        }
        
        self._generate_report(results)
        return results
    
    def _check_system_resources(self) -> Dict[str, Any]:
        """检查系统资源"""
        print("📊 检查系统资源...")
        
        # CPU信息
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 内存信息
        memory = psutil.virtual_memory()
        
        # 磁盘信息
        disk = psutil.disk_usage('/')
        
        system_info = {
            "cpu_count": cpu_count,
            "cpu_frequency_mhz": cpu_freq.current if cpu_freq else 0,
            "cpu_usage_percent": cpu_percent,
            "memory_total_gb": round(memory.total / 1024**3, 2),
            "memory_available_gb": round(memory.available / 1024**3, 2),
            "memory_usage_percent": memory.percent,
            "disk_free_gb": round(disk.free / 1024**3, 2)
        }
        
        # 检查资源问题
        if cpu_percent > 80:
            self.issues.append(f"CPU使用率过高: {cpu_percent:.1f}%")
            self.recommendations.append("关闭其他占用CPU的程序")
        
        if memory.percent > 85:
            self.issues.append(f"内存使用率过高: {memory.percent:.1f}%")
            self.recommendations.append("关闭其他占用内存的程序")
        
        if disk.free < 1024**3:  # 小于1GB
            self.issues.append(f"磁盘空间不足: {disk.free/1024**3:.1f}GB")
            self.recommendations.append("清理磁盘空间，特别是临时文件")
        
        print(f"   CPU: {cpu_count}核 @ {cpu_freq.current if cpu_freq else 0:.0f}MHz, 使用率: {cpu_percent:.1f}%")
        print(f"   内存: {system_info['memory_available_gb']:.1f}GB可用 / {system_info['memory_total_gb']:.1f}GB总计")
        print(f"   磁盘: {system_info['disk_free_gb']:.1f}GB可用")
        
        return system_info
    
    def _analyze_config(self) -> Dict[str, Any]:
        """分析配置设置"""
        print("⚙️  分析配置设置...")
        
        config_analysis = {
            "interval_ms": self.config.interval_ms,
            "fps_max": getattr(self.config, 'fps_max', 30),
            "template_count": len(getattr(self.config, 'template_paths', [])) or 1,
            "grayscale": self.config.grayscale,
            "multi_scale": self.config.multi_scale,
            "roi_enabled": self.config.roi.w > 0 and self.config.roi.h > 0
        }
        
        # 检查配置问题
        if self.config.interval_ms < 500:
            self.issues.append(f"扫描间隔过短: {self.config.interval_ms}ms")
            self.recommendations.append("增加扫描间隔到1000ms以上")
        
        fps_max = getattr(self.config, 'fps_max', 30)
        if fps_max > 30:
            self.issues.append(f"FPS设置过高: {fps_max}")
            self.recommendations.append("降低FPS到20-30之间")
        
        template_count = len(getattr(self.config, 'template_paths', [])) or 1
        if template_count > 5:
            self.issues.append(f"模板数量过多: {template_count}个")
            self.recommendations.append("减少模板数量到3-5个")
        
        if not self.config.grayscale:
            self.issues.append("未启用灰度匹配")
            self.recommendations.append("启用灰度匹配以提高性能")
        
        if not config_analysis["roi_enabled"]:
            self.recommendations.append("设置ROI区域以减少匹配范围")
        
        print(f"   扫描间隔: {self.config.interval_ms}ms")
        print(f"   FPS限制: {fps_max}")
        print(f"   模板数量: {template_count}")
        print(f"   灰度匹配: {'是' if self.config.grayscale else '否'}")
        
        return config_analysis
    
    def _test_capture_performance(self) -> Dict[str, Any]:
        """测试捕获性能"""
        print("📸 测试捕获性能...")
        
        try:
            manager = CaptureManager()
            manager.configure(
                fps=getattr(self.config, 'fps_max', 30),
                include_cursor=getattr(self.config, 'include_cursor', False),
                # 性能诊断默认按窗口捕获路径测试
                border_required=bool(getattr(self.config, 'window_border_required', getattr(self.config, 'border_required', False))),
                restore_minimized=getattr(self.config, 'restore_minimized_noactivate', True)
            )
            
            # 尝试打开窗口捕获
            target_hwnd = getattr(self.config, 'target_hwnd', 0)
            if target_hwnd > 0:
                success = manager.open_window(target_hwnd)
            else:
                target_title = getattr(self.config, 'target_window_title', '')
                if target_title:
                    success = manager.open_window(target_title, True)
                else:
                    print("   ❌ 未配置有效的目标窗口")
                    return {"error": "未配置目标窗口"}
            
            if not success:
                print("   ❌ 无法打开窗口捕获")
                return {"error": "无法打开窗口捕获"}
            
            # 测试捕获性能
            capture_times = []
            frame_sizes = []
            
            print("   正在测试捕获性能...")
            for i in range(10):
                start_time = time.monotonic()
                frame = manager.capture_frame()
                capture_time = (time.monotonic() - start_time) * 1000
                
                if frame is not None:
                    capture_times.append(capture_time)
                    frame_sizes.append(frame.nbytes)
                    print(f"   测试 {i+1}/10: {capture_time:.1f}ms, {frame.nbytes/1024:.1f}KB")
                else:
                    print(f"   测试 {i+1}/10: 捕获失败")
                
                time.sleep(0.1)
            
            manager.close()
            
            if capture_times:
                avg_capture_time = sum(capture_times) / len(capture_times)
                max_capture_time = max(capture_times)
                avg_frame_size = sum(frame_sizes) / len(frame_sizes)
                
                capture_analysis = {
                    "avg_capture_time_ms": round(avg_capture_time, 2),
                    "max_capture_time_ms": round(max_capture_time, 2),
                    "avg_frame_size_kb": round(avg_frame_size / 1024, 2),
                    "success_rate": len(capture_times) / 10 * 100
                }
                
                # 检查捕获性能问题
                if avg_capture_time > 50:
                    self.issues.append(f"捕获耗时过长: 平均{avg_capture_time:.1f}ms")
                    self.recommendations.append("检查目标窗口是否被遮挡或最小化")
                
                if max_capture_time > 100:
                    self.issues.append(f"捕获时间不稳定: 最大{max_capture_time:.1f}ms")
                    self.recommendations.append("检查系统负载和显卡驱动")
                
                print(f"   平均捕获时间: {avg_capture_time:.1f}ms")
                print(f"   最大捕获时间: {max_capture_time:.1f}ms")
                print(f"   平均帧大小: {avg_frame_size/1024:.1f}KB")
                
                return capture_analysis
            else:
                print("   ❌ 所有捕获测试都失败")
                return {"error": "所有捕获测试都失败"}
                
        except Exception as e:
            print(f"   ❌ 捕获测试异常: {e}")
            return {"error": str(e)}
    
    def _analyze_templates(self) -> Dict[str, Any]:
        """分析模板文件"""
        print("🖼️  分析模板文件...")
        
        template_paths = getattr(self.config, 'template_paths', [])
        if not template_paths:
            template_paths = [self.config.template_path]
        
        template_analysis = {
            "template_count": len(template_paths),
            "templates": []
        }
        
        total_size = 0
        for i, path in enumerate(template_paths):
            if not os.path.exists(path):
                self.issues.append(f"模板文件不存在: {path}")
                continue
            
            try:
                img = cv2.imread(path)
                if img is None:
                    self.issues.append(f"无法加载模板: {path}")
                    continue
                
                file_size = os.path.getsize(path)
                total_size += file_size
                
                template_info = {
                    "path": path,
                    "width": img.shape[1],
                    "height": img.shape[0],
                    "channels": img.shape[2] if len(img.shape) > 2 else 1,
                    "file_size_kb": round(file_size / 1024, 2)
                }
                
                template_analysis["templates"].append(template_info)
                
                # 检查模板大小
                if img.shape[0] > 200 or img.shape[1] > 200:
                    self.issues.append(f"模板{i+1}尺寸过大: {img.shape[1]}x{img.shape[0]}")
                    self.recommendations.append(f"缩小模板{i+1}到200x200像素以内")
                
                print(f"   模板{i+1}: {img.shape[1]}x{img.shape[0]}, {file_size/1024:.1f}KB")
                
            except Exception as e:
                self.issues.append(f"分析模板{i+1}失败: {e}")
        
        template_analysis["total_size_kb"] = round(total_size / 1024, 2)
        
        if total_size > 1024 * 1024:  # 大于1MB
            self.issues.append(f"模板文件总大小过大: {total_size/1024/1024:.1f}MB")
            self.recommendations.append("压缩模板文件或减少模板数量")
        
        return template_analysis
    
    def _test_io_performance(self) -> Dict[str, Any]:
        """测试IO性能"""
        print("💾 测试IO性能...")
        
        try:
            # 测试临时文件创建和删除性能
            temp_dir = tempfile.mkdtemp(prefix='perf_test_')
            
            io_times = []
            for i in range(5):
                start_time = time.monotonic()
                
                # 创建临时文件
                temp_file = os.path.join(temp_dir, f'test_{i}.png')
                test_img = np.zeros((100, 100, 3), dtype=np.uint8)
                cv2.imwrite(temp_file, test_img)
                
                # 读取文件
                img = cv2.imread(temp_file)
                
                # 删除文件
                os.unlink(temp_file)
                
                io_time = (time.monotonic() - start_time) * 1000
                io_times.append(io_time)
                print(f"   IO测试 {i+1}/5: {io_time:.1f}ms")
            
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            avg_io_time = sum(io_times) / len(io_times)
            max_io_time = max(io_times)
            
            io_analysis = {
                "avg_io_time_ms": round(avg_io_time, 2),
                "max_io_time_ms": round(max_io_time, 2)
            }
            
            # 检查IO性能问题
            if avg_io_time > 20:
                self.issues.append(f"IO操作耗时过长: 平均{avg_io_time:.1f}ms")
                self.recommendations.append("检查磁盘性能，考虑使用SSD")
            
            if max_io_time > 50:
                self.issues.append(f"IO操作不稳定: 最大{max_io_time:.1f}ms")
                self.recommendations.append("检查磁盘碎片和系统负载")
            
            print(f"   平均IO时间: {avg_io_time:.1f}ms")
            print(f"   最大IO时间: {max_io_time:.1f}ms")
            
            return io_analysis
            
        except Exception as e:
            print(f"   ❌ IO测试异常: {e}")
            return {"error": str(e)}
    
    def _generate_report(self, results: Dict[str, Any]):
        """生成诊断报告"""
        print("\n" + "="*60)
        print("📋 诊断报告")
        print("="*60)
        
        if self.issues:
            print("⚠️  发现的问题:")
            for i, issue in enumerate(self.issues, 1):
                print(f"   {i}. {issue}")
        else:
            print("✅ 未发现明显的性能问题")
        
        if self.recommendations:
            print("\n💡 优化建议:")
            for i, rec in enumerate(self.recommendations, 1):
                print(f"   {i}. {rec}")
        
        print("\n🔧 通用优化建议:")
        print("   • 增加扫描间隔到1500ms以上")
        print("   • 启用灰度匹配模式")
        print("   • 设置合适的ROI区域")
        print("   • 减少模板数量到3-5个")
        print("   • 确保目标窗口不被遮挡")
        print("   • 关闭不必要的后台程序")
        
        print("="*60)


def main():
    """主函数"""
    try:
        diagnostic = PerformanceDiagnostic()
        results = diagnostic.run_full_diagnostic()
        
        # 如果有性能监控数据，也显示出来
        try:
            print("\n📈 当前性能监控数据:")
            print_performance_report()
        except:
            pass
            
    except Exception as e:
        print(f"❌ 诊断过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

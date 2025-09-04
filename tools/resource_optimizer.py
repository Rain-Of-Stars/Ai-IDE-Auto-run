# -*- coding: utf-8 -*-
"""
资源优化器 - 自动检测系统资源并应用最佳配置
主要功能：
1. 检测系统资源状况
2. 自动选择最佳性能配置
3. 优化样式和图标加载
4. 监控资源使用情况
"""
import os
import sys
import psutil
import time
from typing import Dict, Any, Optional
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from auto_approve.logger_manager import get_logger
from auto_approve.performance_config import PerformanceConfigManager


class ResourceOptimizer:
    """资源优化器"""
    
    def __init__(self):
        self.logger = get_logger()
        self.config_manager = PerformanceConfigManager()
        self.system_info = {}
        
    def analyze_system_resources(self) -> Dict[str, Any]:
        """分析系统资源"""
        try:
            # CPU信息
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存信息
            memory = psutil.virtual_memory()
            
            # 磁盘信息
            disk = psutil.disk_usage('.')
            
            self.system_info = {
                "cpu_count": cpu_count,
                "cpu_frequency_mhz": cpu_freq.current if cpu_freq else 0,
                "cpu_usage_percent": cpu_percent,
                "memory_total_gb": round(memory.total / 1024**3, 2),
                "memory_available_gb": round(memory.available / 1024**3, 2),
                "memory_usage_percent": memory.percent,
                "disk_free_gb": round(disk.free / 1024**3, 2)
            }
            
            self.logger.info(f"系统资源分析完成: CPU={cpu_count}核, 内存={self.system_info['memory_total_gb']}GB")
            return self.system_info
            
        except Exception as e:
            self.logger.error(f"系统资源分析失败: {e}")
            return {}
    
    def recommend_performance_profile(self) -> str:
        """推荐性能配置档案"""
        if not self.system_info:
            self.analyze_system_resources()
        
        # 根据系统资源推荐配置
        memory_gb = self.system_info.get('memory_total_gb', 4)
        cpu_count = self.system_info.get('cpu_count', 2)
        cpu_usage = self.system_info.get('cpu_usage_percent', 50)
        memory_usage = self.system_info.get('memory_usage_percent', 50)
        
        # 判断系统负载
        if memory_gb <= 4 or cpu_count <= 2 or memory_usage > 80 or cpu_usage > 70:
            profile = 'minimal'
            reason = "系统资源较低或负载较高"
        elif memory_gb <= 8 or cpu_count <= 4 or memory_usage > 60 or cpu_usage > 50:
            profile = 'low_resource'
            reason = "系统资源中等"
        elif memory_gb <= 16 or cpu_count <= 8:
            profile = 'balanced'
            reason = "系统资源良好"
        else:
            profile = 'high_performance'
            reason = "系统资源充足"
        
        self.logger.info(f"推荐性能配置: {profile} ({reason})")
        return profile
    
    def optimize_styles(self) -> str:
        """优化样式文件选择"""
        profile = self.recommend_performance_profile()
        
        # 根据性能配置选择样式文件
        style_mapping = {
            'minimal': 'minimal.qss',
            'low_resource': 'minimal.qss',
            'balanced': 'modern_flat_lite.qss',
            'high_performance': 'modern_flat.qss'
        }
        
        recommended_style = style_mapping.get(profile, 'minimal.qss')
        self.logger.info(f"推荐样式文件: {recommended_style}")
        return recommended_style
    
    def optimize_icon_cache(self) -> int:
        """优化图标缓存大小"""
        profile = self.recommend_performance_profile()
        
        # 根据性能配置设置图标缓存大小
        cache_mapping = {
            'minimal': 5,
            'low_resource': 8,
            'balanced': 15,
            'high_performance': 25
        }
        
        cache_size = cache_mapping.get(profile, 5)
        self.logger.info(f"推荐图标缓存大小: {cache_size}")
        return cache_size
    
    def apply_optimizations(self):
        """应用所有优化"""
        self.logger.info("开始应用资源优化...")
        
        # 分析系统资源
        self.analyze_system_resources()
        
        # 推荐并应用性能配置
        profile = self.recommend_performance_profile()
        self.config_manager.set_profile(profile)
        
        # 优化图标缓存
        cache_size = self.optimize_icon_cache()
        try:
            from auto_approve.menu_icons import MenuIconManager
            MenuIconManager._max_cache_size = cache_size
        except ImportError:
            pass
        
        self.logger.info("资源优化应用完成")
    
    def generate_optimization_report(self) -> str:
        """生成优化报告"""
        if not self.system_info:
            self.analyze_system_resources()
        
        profile = self.recommend_performance_profile()
        style = self.optimize_styles()
        cache_size = self.optimize_icon_cache()
        
        report = [
            "🔧 资源优化报告",
            "=" * 50,
            "",
            "📊 系统资源状况:",
            f"   • CPU: {self.system_info.get('cpu_count', 'N/A')}核 @ {self.system_info.get('cpu_frequency_mhz', 'N/A')}MHz",
            f"   • 内存: {self.system_info.get('memory_total_gb', 'N/A')}GB (使用率: {self.system_info.get('memory_usage_percent', 'N/A')}%)",
            f"   • CPU使用率: {self.system_info.get('cpu_usage_percent', 'N/A')}%",
            "",
            "⚙️ 推荐配置:",
            f"   • 性能档案: {profile}",
            f"   • 样式文件: {style}",
            f"   • 图标缓存: {cache_size}个",
            "",
            "💡 优化建议:",
        ]
        
        # 添加具体建议
        memory_usage = self.system_info.get('memory_usage_percent', 0)
        cpu_usage = self.system_info.get('cpu_usage_percent', 0)
        
        if memory_usage > 80:
            report.append("   • 内存使用率较高，建议关闭其他程序")
        if cpu_usage > 70:
            report.append("   • CPU使用率较高，建议使用极简模式")
        if self.system_info.get('memory_total_gb', 0) <= 4:
            report.append("   • 系统内存较少，建议升级硬件或使用极简模式")
        
        if len(report) == len(report) - 1:  # 没有添加建议
            report.append("   • 系统资源状况良好，当前配置已优化")
        
        return "\n".join(report)


def main():
    """主函数 - 运行资源优化"""
    print("🔧 AI-IDE-Auto-Run 资源优化器")
    print("=" * 50)
    
    optimizer = ResourceOptimizer()
    
    # 生成并显示优化报告
    report = optimizer.generate_optimization_report()
    print(report)
    
    # 应用优化
    print("\n正在应用优化...")
    optimizer.apply_optimizations()
    print("✓ 优化完成！")


if __name__ == "__main__":
    main()

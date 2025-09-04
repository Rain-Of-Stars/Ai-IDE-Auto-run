# -*- coding: utf-8 -*-
"""
UI启动卡顿诊断工具
专门分析和解决托盘应用初始卡顿问题
"""
from __future__ import annotations
import os
import sys
import time
import threading
from typing import List, Dict, Tuple

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

class UIStartupDiagnostic:
    """UI启动卡顿诊断器"""
    
    def __init__(self):
        self.issues_found = []
        self.recommendations = []
        
    def diagnose_startup_lag(self) -> Dict[str, any]:
        """诊断启动卡顿问题"""
        print("🔍 开始诊断UI启动卡顿问题...")
        print("=" * 60)
        
        # 1. 检查图标创建性能
        self._check_icon_creation_performance()
        
        # 2. 检查QSS样式加载
        self._check_qss_loading()
        
        # 3. 检查模块导入顺序
        self._check_module_import_order()
        
        # 4. 检查同步阻塞操作
        self._check_blocking_operations()
        
        # 5. 检查菜单创建过程
        self._check_menu_creation()
        
        # 6. 检查性能优化设置
        self._check_performance_settings()
        
        return {
            "issues": self.issues_found,
            "recommendations": self.recommendations
        }
    
    def _check_icon_creation_performance(self):
        """检查图标创建性能"""
        print("📊 检查图标创建性能...")
        
        try:
            from auto_approve.menu_icons import create_menu_icon, MenuIconManager
            
            # 测试图标创建时间
            start_time = time.time()
            
            # 创建多个图标测试
            icons = []
            for icon_type in ["status", "play", "stop", "settings", "log", "quit", "screen"]:
                icon_start = time.time()
                icon = create_menu_icon(icon_type, 20, "#FF4444")
                icon_duration = (time.time() - icon_start) * 1000
                icons.append((icon_type, icon_duration))
                
                if icon_duration > 50:  # 超过50ms认为较慢
                    self.issues_found.append(f"图标创建较慢: {icon_type} 耗时 {icon_duration:.1f}ms")
            
            total_duration = (time.time() - start_time) * 1000
            print(f"   总图标创建时间: {total_duration:.1f}ms")
            
            if total_duration > 200:
                self.issues_found.append(f"图标创建总时间过长: {total_duration:.1f}ms")
                self.recommendations.append("优化图标创建: 使用更简单的绘制逻辑或预缓存图标")
            
            # 检查图标缓存
            cache_size = len(MenuIconManager._icon_cache)
            print(f"   图标缓存大小: {cache_size}")
            
        except Exception as e:
            self.issues_found.append(f"图标创建测试失败: {e}")
    
    def _check_qss_loading(self):
        """检查QSS样式加载"""
        print("🎨 检查QSS样式加载...")
        
        qss_path = os.path.join(os.path.dirname(__file__), "..", "assets", "styles", "modern_flat.qss")
        
        if os.path.exists(qss_path):
            try:
                start_time = time.time()
                with open(qss_path, "r", encoding="utf-8") as f:
                    content = f.read()
                load_duration = (time.time() - start_time) * 1000
                
                print(f"   QSS文件大小: {len(content)} 字符")
                print(f"   QSS加载时间: {load_duration:.1f}ms")
                
                if load_duration > 100:
                    self.issues_found.append(f"QSS加载较慢: {load_duration:.1f}ms")
                    self.recommendations.append("优化QSS文件: 简化样式或分割为多个文件")
                
                if len(content) > 50000:  # 超过50KB
                    self.issues_found.append(f"QSS文件过大: {len(content)} 字符")
                    self.recommendations.append("减少QSS文件大小: 移除不必要的样式")
                    
            except Exception as e:
                self.issues_found.append(f"QSS加载失败: {e}")
        else:
            print("   QSS文件不存在，使用默认样式")
    
    def _check_module_import_order(self):
        """检查模块导入顺序"""
        print("📦 检查模块导入顺序...")
        
        # 检查主程序中的导入
        main_file = os.path.join(os.path.dirname(__file__), "..", "main_auto_approve.py")
        if os.path.exists(main_file):
            try:
                with open(main_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 检查是否有延迟导入
                if "# 延迟导入" in content:
                    print("   ✅ 发现延迟导入优化")
                else:
                    self.issues_found.append("缺少延迟导入优化")
                    self.recommendations.append("使用延迟导入: 将非关键模块的导入放到使用时")
                
                # 检查重型模块导入
                heavy_imports = ["numpy", "cv2", "opencv", "scipy", "matplotlib"]
                for heavy in heavy_imports:
                    if f"import {heavy}" in content and "延迟导入" not in content:
                        self.issues_found.append(f"重型模块 {heavy} 在启动时导入")
                        self.recommendations.append(f"延迟导入 {heavy}: 只在需要时导入")
                        
            except Exception as e:
                self.issues_found.append(f"检查导入顺序失败: {e}")
    
    def _check_blocking_operations(self):
        """检查同步阻塞操作"""
        print("⏳ 检查同步阻塞操作...")
        
        # 检查配置加载
        try:
            from auto_approve.config_manager import load_config
            
            start_time = time.time()
            config = load_config()
            load_duration = (time.time() - start_time) * 1000
            
            print(f"   配置加载时间: {load_duration:.1f}ms")
            
            if load_duration > 100:
                self.issues_found.append(f"配置加载较慢: {load_duration:.1f}ms")
                self.recommendations.append("优化配置加载: 使用异步加载或缓存")
                
        except Exception as e:
            self.issues_found.append(f"配置加载测试失败: {e}")
        
        # 检查文件IO操作
        config_file = os.path.join(os.path.dirname(__file__), "..", "config.json")
        if os.path.exists(config_file):
            file_size = os.path.getsize(config_file)
            print(f"   配置文件大小: {file_size} 字节")
            
            if file_size > 10000:  # 超过10KB
                self.issues_found.append(f"配置文件过大: {file_size} 字节")
                self.recommendations.append("优化配置文件: 移除不必要的配置项")
    
    def _check_menu_creation(self):
        """检查菜单创建过程"""
        print("🍽️ 检查菜单创建过程...")
        
        try:
            from PySide6 import QtWidgets, QtGui, QtCore
            
            # 测试菜单创建时间
            start_time = time.time()
            
            # 创建菜单
            menu = QtWidgets.QMenu()
            menu.setObjectName("TestMenu")
            
            # 添加多个菜单项
            for i in range(10):
                action = QtGui.QAction(f"测试菜单项 {i+1}")
                menu.addAction(action)
            
            creation_duration = (time.time() - start_time) * 1000
            print(f"   菜单创建时间: {creation_duration:.1f}ms")
            
            if creation_duration > 100:
                self.issues_found.append(f"菜单创建较慢: {creation_duration:.1f}ms")
                self.recommendations.append("优化菜单创建: 简化菜单结构或延迟创建")
                
        except Exception as e:
            self.issues_found.append(f"菜单创建测试失败: {e}")
    
    def _check_performance_settings(self):
        """检查性能优化设置"""
        print("⚡ 检查性能优化设置...")
        
        try:
            from auto_approve.config_manager import load_config
            config = load_config()
            
            # 检查关键性能设置
            performance_issues = []
            
            if getattr(config, 'interval_ms', 1000) < 1000:
                performance_issues.append(f"扫描间隔过短: {config.interval_ms}ms")
            
            if getattr(config, 'multi_scale', False):
                performance_issues.append("多尺度匹配已启用，会增加计算量")
            
            if getattr(config, 'debug_mode', False):
                performance_issues.append("调试模式已启用，会影响性能")
            
            template_count = len(getattr(config, 'template_paths', []))
            if template_count > 5:
                performance_issues.append(f"模板数量过多: {template_count}个")
            
            if performance_issues:
                self.issues_found.extend(performance_issues)
                self.recommendations.append("优化性能设置: 调整扫描间隔、减少模板数量、关闭调试模式")
            else:
                print("   ✅ 性能设置良好")
                
        except Exception as e:
            self.issues_found.append(f"性能设置检查失败: {e}")
    
    def generate_optimization_plan(self) -> str:
        """生成优化方案"""
        report = []
        report.append("🛠️ UI启动卡顿优化方案")
        report.append("=" * 60)
        
        if not self.issues_found:
            report.append("✅ 未发现明显的性能问题")
            report.append("💡 如果仍有卡顿，可能是系统级别的问题")
            return "\n".join(report)
        
        report.append(f"🚨 发现 {len(self.issues_found)} 个问题:")
        for i, issue in enumerate(self.issues_found, 1):
            report.append(f"   {i}. {issue}")
        
        report.append("")
        report.append("💡 优化建议:")
        for i, rec in enumerate(self.recommendations, 1):
            report.append(f"   {i}. {rec}")
        
        report.append("")
        report.append("🔧 具体优化步骤:")
        
        # 根据问题类型给出具体步骤
        if any("图标" in issue for issue in self.issues_found):
            report.append("   📊 图标优化:")
            report.append("     - 在TrayApp.__init__中预创建所有图标")
            report.append("     - 使用更简单的图标绘制算法")
            report.append("     - 考虑使用PNG图标文件替代代码绘制")
        
        if any("QSS" in issue for issue in self.issues_found):
            report.append("   🎨 样式优化:")
            report.append("     - 简化QSS样式表")
            report.append("     - 移除不必要的样式规则")
            report.append("     - 考虑异步加载样式")
        
        if any("导入" in issue for issue in self.issues_found):
            report.append("   📦 导入优化:")
            report.append("     - 将重型模块导入移到使用时")
            report.append("     - 使用TYPE_CHECKING进行类型导入")
            report.append("     - 优化模块导入顺序")
        
        if any("菜单" in issue for issue in self.issues_found):
            report.append("   🍽️ 菜单优化:")
            report.append("     - 简化菜单结构")
            report.append("     - 延迟创建非关键菜单项")
            report.append("     - 使用更轻量的菜单实现")
        
        report.append("")
        report.append("⚡ 立即可执行的优化:")
        report.append("   1. 在main_auto_approve.py中添加更多延迟导入")
        report.append("   2. 优化图标创建逻辑，减少绘制复杂度")
        report.append("   3. 简化QSS样式表，移除不必要的规则")
        report.append("   4. 将非关键初始化操作移到后台线程")
        
        return "\n".join(report)

def main():
    """主函数"""
    print("🔍 UI启动卡顿诊断工具")
    print("=" * 60)
    
    diagnostic = UIStartupDiagnostic()
    
    # 执行诊断
    results = diagnostic.diagnose_startup_lag()
    
    print("\n" + "="*60)
    
    # 生成优化方案
    optimization_plan = diagnostic.generate_optimization_plan()
    print(optimization_plan)
    
    print("\n✅ 诊断完成")
    print("💡 建议按照优化方案逐步改进，每次改进后测试效果")

if __name__ == "__main__":
    main()

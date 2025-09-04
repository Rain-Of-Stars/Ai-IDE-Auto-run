# -*- coding: utf-8 -*-
"""
UI卡顿分析器 - 专门分析托盘菜单初始卡顿问题
通过详细的时间测量来定位UI响应慢的原因
"""
from __future__ import annotations
import os
import sys
import time
import threading
from typing import List, Dict
from dataclasses import dataclass

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

@dataclass
class UIOperation:
    """UI操作记录"""
    name: str
    start_time: float
    end_time: float
    duration_ms: float
    thread_id: int
    details: str = ""

class UILagAnalyzer:
    """UI卡顿分析器"""
    
    def __init__(self):
        self.operations: List[UIOperation] = []
        self.start_time = time.time()
        
    def measure_ui_operation(self, operation_name: str, details: str = ""):
        """测量UI操作的装饰器"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start = time.time()
                thread_id = threading.get_ident()
                
                print(f"🔄 开始: {operation_name}")
                
                try:
                    result = func(*args, **kwargs)
                    success = True
                except Exception as e:
                    print(f"❌ {operation_name} 失败: {e}")
                    result = None
                    success = False
                
                end = time.time()
                duration_ms = (end - start) * 1000
                
                operation = UIOperation(
                    name=operation_name,
                    start_time=start - self.start_time,
                    end_time=end - self.start_time,
                    duration_ms=duration_ms,
                    thread_id=thread_id,
                    details=details + (f" (失败: {str(e) if not success else ''})" if not success else "")
                )
                self.operations.append(operation)
                
                # 根据耗时给出不同的提示
                if duration_ms > 500:
                    print(f"🐌 {operation_name}: {duration_ms:.1f}ms (严重卡顿)")
                elif duration_ms > 200:
                    print(f"⚠️ {operation_name}: {duration_ms:.1f}ms (轻微卡顿)")
                elif duration_ms > 100:
                    print(f"⏱️ {operation_name}: {duration_ms:.1f}ms (稍慢)")
                else:
                    print(f"✅ {operation_name}: {duration_ms:.1f}ms")
                
                return result
            return wrapper
        return decorator
    
    def analyze_ui_performance(self) -> Dict[str, any]:
        """分析UI性能"""
        if not self.operations:
            return {"error": "没有UI操作数据"}
        
        # 找出最慢的操作
        slow_operations = [op for op in self.operations if op.duration_ms > 100]
        slow_operations.sort(key=lambda x: x.duration_ms, reverse=True)
        
        # 计算总时间
        total_time = max(op.end_time for op in self.operations) if self.operations else 0
        
        # 分析操作类型
        operation_types = {}
        for op in self.operations:
            op_type = op.name.split("_")[0] if "_" in op.name else op.name
            if op_type not in operation_types:
                operation_types[op_type] = {"count": 0, "total_time": 0, "max_time": 0}
            
            operation_types[op_type]["count"] += 1
            operation_types[op_type]["total_time"] += op.duration_ms
            operation_types[op_type]["max_time"] = max(operation_types[op_type]["max_time"], op.duration_ms)
        
        return {
            "total_operations": len(self.operations),
            "slow_operations": slow_operations,
            "total_time_seconds": total_time,
            "operation_types": operation_types,
            "timeline": self.operations
        }
    
    def generate_report(self) -> str:
        """生成UI性能报告"""
        analysis = self.analyze_ui_performance()
        
        if "error" in analysis:
            return f"❌ 分析失败: {analysis['error']}"
        
        report = []
        report.append("🖥️ UI性能分析报告")
        report.append("=" * 60)
        
        # 总体统计
        report.append(f"📊 总操作数: {analysis['total_operations']}")
        report.append(f"⏱️ 总耗时: {analysis['total_time_seconds']:.2f}秒")
        report.append(f"🐌 慢操作数: {len(analysis['slow_operations'])}")
        report.append("")
        
        # 慢操作详情
        if analysis['slow_operations']:
            report.append("🚨 发现的UI卡顿操作:")
            for i, op in enumerate(analysis['slow_operations'][:10]):  # 显示前10个最慢的
                report.append(f"   {i+1}. {op.name}: {op.duration_ms:.1f}ms")
                if op.details:
                    report.append(f"      详情: {op.details}")
            report.append("")
        
        # 操作类型统计
        report.append("📈 操作类型统计:")
        for op_type, stats in analysis['operation_types'].items():
            avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
            report.append(f"   • {op_type}:")
            report.append(f"     - 次数: {stats['count']}")
            report.append(f"     - 平均耗时: {avg_time:.1f}ms")
            report.append(f"     - 最大耗时: {stats['max_time']:.1f}ms")
        
        # 时间线分析
        report.append("")
        report.append("⏰ 操作时间线 (前20个操作):")
        for i, op in enumerate(analysis['timeline'][:20]):
            status = "🐌" if op.duration_ms > 200 else "⚠️" if op.duration_ms > 100 else "✅"
            report.append(f"   {i+1:2d}. {status} {op.start_time:.2f}s: {op.name} ({op.duration_ms:.1f}ms)")
        
        # 优化建议
        report.append("")
        report.append("💡 优化建议:")
        
        # 根据分析结果给出具体建议
        icon_operations = [op for op in analysis['slow_operations'] if 'icon' in op.name.lower()]
        if icon_operations:
            report.append("   • 图标创建较慢，考虑:")
            report.append("     - 使用图标缓存")
            report.append("     - 简化图标绘制逻辑")
            report.append("     - 延迟创建非关键图标")
        
        menu_operations = [op for op in analysis['slow_operations'] if 'menu' in op.name.lower()]
        if menu_operations:
            report.append("   • 菜单创建较慢，考虑:")
            report.append("     - 简化菜单结构")
            report.append("     - 延迟加载菜单项")
            report.append("     - 优化菜单样式应用")
        
        theme_operations = [op for op in analysis['slow_operations'] if 'theme' in op.name.lower() or 'style' in op.name.lower()]
        if theme_operations:
            report.append("   • 主题应用较慢，考虑:")
            report.append("     - 简化QSS样式")
            report.append("     - 缓存样式表")
            report.append("     - 异步应用非关键样式")
        
        if analysis['total_time_seconds'] > 2.0:
            report.append("   • 总启动时间过长，考虑:")
            report.append("     - 延迟初始化非关键组件")
            report.append("     - 使用异步加载")
            report.append("     - 优化模块导入顺序")
        
        return "\n".join(report)

def test_ui_operations():
    """测试UI操作性能"""
    analyzer = UILagAnalyzer()
    
    print("🔍 开始UI卡顿分析...")
    print("=" * 50)
    
    # 模拟各种UI操作
    @analyzer.measure_ui_operation("导入Qt模块", "PySide6核心模块")
    def import_qt():
        try:
            from PySide6 import QtWidgets, QtGui, QtCore
            time.sleep(0.1)  # 模拟导入时间
        except ImportError:
            print("⚠️ 无法导入PySide6")
    
    @analyzer.measure_ui_operation("创建应用程序", "QApplication实例")
    def create_app():
        try:
            from PySide6 import QtWidgets
            app = QtWidgets.QApplication.instance()
            if app is None:
                app = QtWidgets.QApplication([])
            time.sleep(0.05)
            return app
        except Exception:
            return None
    
    @analyzer.measure_ui_operation("加载QSS样式", "modern_flat.qss")
    def load_qss():
        qss_path = os.path.join(os.path.dirname(__file__), "..", "assets", "styles", "modern_flat.qss")
        if os.path.exists(qss_path):
            try:
                with open(qss_path, "r", encoding="utf-8") as f:
                    content = f.read()
                time.sleep(0.02)  # 模拟样式解析时间
                return len(content)
            except Exception as e:
                print(f"加载QSS失败: {e}")
        return 0
    
    @analyzer.measure_ui_operation("创建菜单图标_status", "状态图标20px")
    def create_status_icon():
        try:
            from auto_approve.menu_icons import create_menu_icon
            icon = create_menu_icon("status", 20, "#FF4444")
            time.sleep(0.01)  # 模拟图标创建时间
            return icon
        except Exception as e:
            print(f"创建状态图标失败: {e}")
            return None
    
    @analyzer.measure_ui_operation("创建菜单图标_play", "播放图标20px")
    def create_play_icon():
        try:
            from auto_approve.menu_icons import create_menu_icon
            icon = create_menu_icon("play", 20, "#00C851")
            time.sleep(0.01)
            return icon
        except Exception as e:
            print(f"创建播放图标失败: {e}")
            return None
    
    @analyzer.measure_ui_operation("创建菜单图标_stop", "停止图标20px")
    def create_stop_icon():
        try:
            from auto_approve.menu_icons import create_menu_icon
            icon = create_menu_icon("stop", 20, "#FF4444")
            time.sleep(0.01)
            return icon
        except Exception as e:
            print(f"创建停止图标失败: {e}")
            return None
    
    @analyzer.measure_ui_operation("创建菜单图标_settings", "设置图标20px")
    def create_settings_icon():
        try:
            from auto_approve.menu_icons import create_menu_icon
            icon = create_menu_icon("settings", 20, "#808080")
            time.sleep(0.015)  # 设置图标稍复杂
            return icon
        except Exception as e:
            print(f"创建设置图标失败: {e}")
            return None
    
    @analyzer.measure_ui_operation("创建托盘菜单", "PersistentTrayMenu")
    def create_tray_menu():
        try:
            from PySide6 import QtWidgets, QtCore
            menu = QtWidgets.QMenu()
            menu.setWindowFlags(QtCore.Qt.Popup)
            time.sleep(0.03)
            return menu
        except Exception as e:
            print(f"创建托盘菜单失败: {e}")
            return None
    
    @analyzer.measure_ui_operation("添加菜单项", "状态、开始、停止等")
    def add_menu_actions():
        try:
            from PySide6 import QtGui
            actions = []
            for i in range(8):  # 模拟8个菜单项
                action = QtGui.QAction(f"菜单项 {i+1}")
                actions.append(action)
                time.sleep(0.005)  # 每个菜单项5ms
            return actions
        except Exception as e:
            print(f"添加菜单项失败: {e}")
            return []
    
    @analyzer.measure_ui_operation("应用UI增强", "窗口效果和动画")
    def apply_ui_enhancements():
        time.sleep(0.02)  # 模拟UI增强应用时间
    
    @analyzer.measure_ui_operation("初始化性能优化器", "TrayMenuOptimizer")
    def init_optimizer():
        time.sleep(0.01)  # 模拟优化器初始化
    
    # 执行所有测试操作
    import_qt()
    app = create_app()
    load_qss()
    create_status_icon()
    create_play_icon()
    create_stop_icon()
    create_settings_icon()
    create_tray_menu()
    add_menu_actions()
    apply_ui_enhancements()
    init_optimizer()
    
    # 模拟一些额外的初始化延迟
    @analyzer.measure_ui_operation("其他初始化", "配置加载、状态同步等")
    def other_init():
        time.sleep(0.08)  # 模拟其他初始化操作
    
    other_init()
    
    return analyzer

if __name__ == "__main__":
    print("🖥️ UI卡顿分析器")
    print("=" * 50)
    
    analyzer = test_ui_operations()
    
    print("\n" + "="*50)
    report = analyzer.generate_report()
    print(report)
    
    print("\n✅ UI分析完成")
    print("💡 提示: 重点关注耗时超过100ms的操作")

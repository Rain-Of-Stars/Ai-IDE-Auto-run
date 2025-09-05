# -*- coding: utf-8 -*-
"""
性能警告处理模块

统一处理各种性能警告和异常情况
"""

import time
from typing import Optional, Dict, Any, Callable
from auto_approve.logger_manager import get_logger


class PerformanceAlertHandler:
    """性能警告处理器"""
    
    def __init__(self):
        self.logger = get_logger()
        self.alert_callbacks = {}  # 警告类型 -> 回调函数
        self.alert_history = []  # 警告历史
        self.max_history = 100  # 最大历史记录数
        
        # 警告阈值
        self.thresholds = {
            'cpu_high': 80.0,
            'memory_high': 500.0,  # MB
            'scan_slow': 200.0,    # ms
            'match_slow': 100.0,   # ms
            'fps_low': 5.0
        }
    
    def register_callback(self, alert_type: str, callback: Callable[[str, float], None]):
        """注册警告回调函数"""
        self.alert_callbacks[alert_type] = callback
    
    def handle_performance_alert(self, alert_type: str, value: float, 
                                context: str = "", extra_data: Dict[str, Any] = None):
        """统一的性能警告处理函数
        
        Args:
            alert_type: 警告类型 (cpu_high, memory_high, scan_slow, etc.)
            value: 当前值
            context: 上下文信息 (main_app, test, etc.)
            extra_data: 额外数据
        """
        timestamp = time.time()
        
        # 记录警告
        alert_record = {
            'timestamp': timestamp,
            'alert_type': alert_type,
            'value': value,
            'context': context,
            'extra_data': extra_data or {}
        }
        
        self.alert_history.append(alert_record)
        
        # 限制历史记录数量
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]
        
        # 获取阈值
        threshold = self.thresholds.get(alert_type, 0)
        
        # 生成警告消息
        message = self._format_alert_message(alert_type, value, threshold, context)
        
        # 记录日志
        if self._is_critical_alert(alert_type, value):
            self.logger.error(message)
        else:
            self.logger.warning(message)
        
        # 调用注册的回调函数
        if alert_type in self.alert_callbacks:
            try:
                self.alert_callbacks[alert_type](alert_type, value)
            except Exception as e:
                self.logger.error(f"性能警告回调执行失败: {e}")
        
        # 执行默认处理逻辑
        self._execute_default_handling(alert_type, value, context)
    
    def _format_alert_message(self, alert_type: str, value: float, 
                             threshold: float, context: str) -> str:
        """格式化警告消息"""
        context_str = f"[{context}] " if context else ""
        
        message_templates = {
            'cpu_high': f"{context_str}CPU使用率过高: {value:.1f}% (阈值: {threshold:.1f}%)",
            'memory_high': f"{context_str}内存使用过高: {value:.1f}MB (阈值: {threshold:.1f}MB)",
            'scan_slow': f"{context_str}扫描耗时过长: {value:.1f}ms (阈值: {threshold:.1f}ms)",
            'match_slow': f"{context_str}匹配耗时过长: {value:.1f}ms (阈值: {threshold:.1f}ms)",
            'fps_low': f"{context_str}帧率过低: {value:.1f}fps (阈值: {threshold:.1f}fps)",
            'capture_fail': f"{context_str}捕获失败: 连续失败 {value:.0f} 次",
            'template_load_fail': f"{context_str}模板加载失败: {value}",
            'process_hang': f"{context_str}进程疑似挂起: 无响应 {value:.1f}秒"
        }
        
        return message_templates.get(alert_type, 
                                   f"{context_str}性能警告 [{alert_type}]: {value}")
    
    def _is_critical_alert(self, alert_type: str, value: float) -> bool:
        """判断是否为严重警告"""
        critical_conditions = {
            'cpu_high': value > 95.0,
            'memory_high': value > 1000.0,  # 1GB
            'scan_slow': value > 500.0,     # 500ms
            'capture_fail': value > 10,     # 连续失败10次
            'process_hang': value > 30.0    # 挂起30秒
        }
        
        return critical_conditions.get(alert_type, False)
    
    def _execute_default_handling(self, alert_type: str, value: float, context: str):
        """执行默认处理逻辑"""
        if alert_type == 'cpu_high' and value > 90.0:
            # CPU过高时的处理
            self.logger.info("CPU使用率过高，建议降低扫描频率")
        
        elif alert_type == 'memory_high' and value > 800.0:
            # 内存过高时的处理
            self.logger.info("内存使用过高，建议清理缓存")
        
        elif alert_type == 'scan_slow' and value > 300.0:
            # 扫描过慢时的处理
            self.logger.info("扫描耗时过长，建议优化模板或ROI设置")
        
        elif alert_type == 'capture_fail' and value > 5:
            # 捕获失败时的处理
            self.logger.info("捕获频繁失败，建议检查窗口状态")
    
    def get_alert_history(self, alert_type: str = None, 
                         since: float = None) -> list:
        """获取警告历史
        
        Args:
            alert_type: 筛选特定类型的警告
            since: 筛选指定时间之后的警告
        
        Returns:
            警告记录列表
        """
        history = self.alert_history
        
        if alert_type:
            history = [record for record in history 
                      if record['alert_type'] == alert_type]
        
        if since:
            history = [record for record in history 
                      if record['timestamp'] >= since]
        
        return history
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """获取警告统计信息"""
        if not self.alert_history:
            return {}
        
        # 按类型统计
        type_counts = {}
        for record in self.alert_history:
            alert_type = record['alert_type']
            type_counts[alert_type] = type_counts.get(alert_type, 0) + 1
        
        # 最近的警告
        recent_alerts = sorted(self.alert_history, 
                              key=lambda x: x['timestamp'], reverse=True)[:5]
        
        return {
            'total_alerts': len(self.alert_history),
            'alert_types': type_counts,
            'recent_alerts': recent_alerts,
            'most_frequent_type': max(type_counts.items(), key=lambda x: x[1])[0] if type_counts else None
        }
    
    def clear_history(self):
        """清空警告历史"""
        self.alert_history.clear()
        self.logger.info("性能警告历史已清空")


# 全局警告处理器实例
_global_alert_handler = None


def get_alert_handler() -> PerformanceAlertHandler:
    """获取全局警告处理器实例"""
    global _global_alert_handler
    if _global_alert_handler is None:
        _global_alert_handler = PerformanceAlertHandler()
    return _global_alert_handler


def handle_performance_alert(alert_type: str, value: float, 
                           context: str = "", extra_data: Dict[str, Any] = None):
    """便捷函数：处理性能警告"""
    handler = get_alert_handler()
    handler.handle_performance_alert(alert_type, value, context, extra_data)


def register_alert_callback(alert_type: str, callback: Callable[[str, float], None]):
    """便捷函数：注册警告回调"""
    handler = get_alert_handler()
    handler.register_callback(alert_type, callback)


def get_alert_statistics() -> Dict[str, Any]:
    """便捷函数：获取警告统计"""
    handler = get_alert_handler()
    return handler.get_alert_statistics()

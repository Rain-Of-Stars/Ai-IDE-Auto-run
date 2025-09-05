# -*- coding: utf-8 -*-
"""
核心业务逻辑模块

包含应用的核心功能：
- 应用状态管理
- 配置管理
- 日志管理
- 扫描进程适配器
"""

# 为了保持向后兼容性，重新导出核心类
try:
    from ..app_state import AppState, get_app_state
    from ..config_manager import AppConfig, load_config, save_config
    from ..logger_manager import get_logger, enable_file_logging
    from ..scanner_process_adapter import ProcessScannerWorker, ScannerProcessAdapter
except ImportError:
    # 如果文件还没有移动，使用原始导入
    pass

__all__ = [
    'AppState', 'get_app_state',
    'AppConfig', 'load_config', 'save_config', 
    'get_logger', 'enable_file_logging',
    'ProcessScannerWorker', 'ScannerProcessAdapter'
]

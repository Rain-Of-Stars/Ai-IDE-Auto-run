# -*- coding: utf-8 -*-
"""
扫描进程适配器

提供与原有ScannerWorker兼容的接口，内部使用独立进程实现
"""

from typing import Optional
from PySide6 import QtCore

from auto_approve.config_manager import AppConfig
from auto_approve.logger_manager import get_logger
from workers.scanner_process import get_global_scanner_manager, ScannerStatus, ScannerHit


class ScannerProcessAdapter(QtCore.QObject):
    """扫描进程适配器
    
    提供与原有ScannerWorker相同的接口，内部使用独立进程实现
    """
    
    # 状态文本（用于托盘提示）
    sig_status = QtCore.Signal(str)
    # 命中信号：score, sx, sy（屏幕坐标）
    sig_hit = QtCore.Signal(float, int, int)
    # 错误或日志文本
    sig_log = QtCore.Signal(str)
    
    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg
        self._logger = get_logger()
        self._running = False
        
        # 获取全局扫描进程管理器
        self._scanner_manager = get_global_scanner_manager()
        
        # 连接信号
        self._scanner_manager.signals.status_updated.connect(self._on_status_updated)
        self._scanner_manager.signals.hit_detected.connect(self._on_hit_detected)
        self._scanner_manager.signals.log_message.connect(self._on_log_message)
        self._scanner_manager.signals.error_occurred.connect(self._on_error_occurred)
        
        self._logger.info("扫描进程适配器初始化完成")
    
    def start(self):
        """启动扫描进程"""
        if self._running:
            self._logger.warning("扫描进程已在运行")
            return
        
        try:
            success = self._scanner_manager.start_scanning(self.cfg)
            if success:
                self._running = True
                self._logger.info("扫描进程启动成功")
            else:
                self._logger.error("扫描进程启动失败")
                self.sig_log.emit("扫描进程启动失败")
                
        except Exception as e:
            self._logger.error(f"启动扫描进程异常: {e}")
            self.sig_log.emit(f"启动扫描进程异常: {e}")
    
    def stop(self):
        """停止扫描进程"""
        if not self._running:
            self._logger.warning("扫描进程未在运行")
            return
        
        try:
            success = self._scanner_manager.stop_scanning()
            if success:
                self._running = False
                self._logger.info("扫描进程停止成功")
            else:
                self._logger.error("扫描进程停止失败")
                
        except Exception as e:
            self._logger.error(f"停止扫描进程异常: {e}")
    
    def update_config(self, new_cfg: AppConfig):
        """更新配置"""
        self.cfg = new_cfg
        
        try:
            self._scanner_manager.update_config(new_cfg)
            self._logger.info("配置更新成功")
        except Exception as e:
            self._logger.error(f"更新配置异常: {e}")
            self.sig_log.emit(f"更新配置异常: {e}")
    
    def isRunning(self) -> bool:
        """检查是否在运行（兼容QThread接口）"""
        return self._running and self._scanner_manager.is_running()
    
    def wait(self, timeout_ms: int = 5000) -> bool:
        """等待进程结束（兼容QThread接口）"""
        # 对于进程，我们只是等待一段时间
        import time
        start_time = time.time()
        while self.isRunning() and (time.time() - start_time) * 1000 < timeout_ms:
            time.sleep(0.1)
        return not self.isRunning()
    
    def terminate(self):
        """强制终止（兼容QThread接口）"""
        self.stop()
    
    def cleanup(self):
        """清理资源"""
        if self._running:
            self.stop()
        
        try:
            self._scanner_manager.cleanup()
            self._logger.info("扫描进程适配器清理完成")
        except Exception as e:
            self._logger.error(f"清理扫描进程适配器异常: {e}")
    
    def _on_status_updated(self, status: ScannerStatus):
        """处理状态更新"""
        try:
            # 构造状态字符串，与原有格式兼容
            if status.running:
                status_text = f"{status.status_text} | 后端: {status.backend}"
                if status.detail:
                    status_text += f" | {status.detail}"
            else:
                status_text = "已停止"
            
            self.sig_status.emit(status_text)
            
        except Exception as e:
            self._logger.error(f"处理状态更新异常: {e}")
    
    def _on_hit_detected(self, hit: ScannerHit):
        """处理命中检测"""
        try:
            self.sig_hit.emit(hit.score, hit.x, hit.y)
        except Exception as e:
            self._logger.error(f"处理命中检测异常: {e}")
    
    def _on_log_message(self, message: str):
        """处理日志消息"""
        try:
            self.sig_log.emit(message)
        except Exception as e:
            self._logger.error(f"处理日志消息异常: {e}")
    
    def _on_error_occurred(self, error: str):
        """处理错误"""
        try:
            self.sig_log.emit(f"扫描进程错误: {error}")
        except Exception as e:
            self._logger.error(f"处理错误异常: {e}")


class ProcessScannerWorker(ScannerProcessAdapter):
    """进程版扫描器工作类
    
    完全兼容原有ScannerWorker接口的进程版本
    """
    
    def __init__(self, cfg: AppConfig):
        super().__init__(cfg)
        self._logger.info("进程版扫描器工作类初始化完成")
    
    def __del__(self):
        """析构函数，确保资源清理"""
        try:
            self.cleanup()
        except:
            pass

# -*- coding: utf-8 -*-
"""
测试独立扫描进程功能

验证扫描进程的启动、停止、通信等功能
"""

import sys
import time
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from PySide6 import QtWidgets, QtCore
from auto_approve.config_manager import AppConfig, load_config
from auto_approve.logger_manager import get_logger, enable_file_logging
from workers.scanner_process import get_global_scanner_manager, ScannerStatus, ScannerHit


class ScannerProcessTester(QtCore.QObject):
    """扫描进程测试器"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger()
        self.scanner_manager = get_global_scanner_manager()
        
        # 连接信号
        self.scanner_manager.signals.status_updated.connect(self.on_status_updated)
        self.scanner_manager.signals.hit_detected.connect(self.on_hit_detected)
        self.scanner_manager.signals.log_message.connect(self.on_log_message)
        self.scanner_manager.signals.error_occurred.connect(self.on_error_occurred)
        
        # 测试配置
        self.test_config = self.create_test_config()
        
        self.logger.info("扫描进程测试器初始化完成")
    
    def create_test_config(self) -> AppConfig:
        """创建测试配置"""
        try:
            # 尝试加载现有配置
            cfg = load_config()
        except:
            # 创建默认配置
            cfg = AppConfig()
        
        # 设置测试参数
        cfg.interval_ms = 1000  # 1秒间隔，便于观察
        cfg.threshold = 0.8
        cfg.grayscale = True
        cfg.use_monitor = False  # 使用窗口捕获
        cfg.window_title = "记事本"  # 测试目标窗口
        cfg.click_delay_ms = 500
        cfg.debug_mode = True
        
        # 设置模板路径（如果存在）
        template_dir = project_root / "templates"
        if template_dir.exists():
            template_files = list(template_dir.glob("*.png"))
            cfg.template_paths = [str(f) for f in template_files[:3]]  # 最多3个模板
        else:
            cfg.template_paths = []
        
        self.logger.info(f"测试配置创建完成，模板数量: {len(cfg.template_paths)}")
        return cfg
    
    def on_status_updated(self, status: ScannerStatus):
        """状态更新处理"""
        self.logger.info(f"状态更新: {status.status_text} | {status.backend} | {status.detail}")
        if status.error_message:
            self.logger.error(f"扫描错误: {status.error_message}")
    
    def on_hit_detected(self, hit: ScannerHit):
        """命中检测处理"""
        self.logger.info(f"检测到命中: 置信度={hit.score:.3f}, 位置=({hit.x}, {hit.y})")
    
    def on_log_message(self, message: str):
        """日志消息处理"""
        self.logger.info(f"扫描进程日志: {message}")
    
    def on_error_occurred(self, error: str):
        """错误处理"""
        self.logger.error(f"扫描进程错误: {error}")
    
    def start_test(self):
        """开始测试"""
        self.logger.info("开始扫描进程测试...")
        print("开始扫描进程测试...")

        # 启动扫描
        try:
            success = self.scanner_manager.start_scanning(self.test_config)
            if success:
                self.logger.info("扫描进程启动成功")
                print("扫描进程启动成功")

                # 设置定时器，10秒后停止测试
                QtCore.QTimer.singleShot(10000, self.stop_test)

                # 设置定时器，5秒后更新配置
                QtCore.QTimer.singleShot(5000, self.update_config_test)

            else:
                self.logger.error("扫描进程启动失败")
                print("扫描进程启动失败")
                QtCore.QTimer.singleShot(1000, self.cleanup_and_exit)
        except Exception as e:
            self.logger.error(f"启动测试异常: {e}")
            print(f"启动测试异常: {e}")
            QtCore.QTimer.singleShot(1000, self.cleanup_and_exit)
    
    def update_config_test(self):
        """测试配置更新"""
        self.logger.info("测试配置更新...")
        
        # 修改配置
        self.test_config.interval_ms = 2000  # 改为2秒间隔
        self.test_config.threshold = 0.7     # 降低阈值
        
        # 更新配置
        self.scanner_manager.update_config(self.test_config)
        self.logger.info("配置更新命令已发送")
    
    def stop_test(self):
        """停止测试"""
        self.logger.info("停止扫描进程测试...")
        
        success = self.scanner_manager.stop_scanning()
        if success:
            self.logger.info("扫描进程停止成功")
        else:
            self.logger.error("扫描进程停止失败")
        
        # 延迟退出，等待清理完成
        QtCore.QTimer.singleShot(3000, self.cleanup_and_exit)
    
    def cleanup_and_exit(self):
        """清理并退出"""
        self.logger.info("清理资源并退出...")
        
        try:
            self.scanner_manager.cleanup()
            self.logger.info("资源清理完成")
        except Exception as e:
            self.logger.error(f"资源清理失败: {e}")
        
        # 退出应用
        QtWidgets.QApplication.instance().quit()


def main():
    """主函数"""
    # 设置UTF-8编码
    os.environ['PYTHONIOENCODING'] = 'utf-8'

    print("开始扫描进程测试...")

    # 创建应用
    app = QtWidgets.QApplication(sys.argv)

    # 启用日志
    enable_file_logging(True)
    logger = get_logger()
    logger.info("扫描进程测试开始")
    print("日志已启用")

    # 创建测试器
    try:
        tester = ScannerProcessTester()
        print("测试器创建成功")
    except Exception as e:
        print(f"创建测试器失败: {e}")
        logger.error(f"创建测试器失败: {e}")
        return 1

    # 延迟启动测试，确保应用完全初始化
    QtCore.QTimer.singleShot(1000, tester.start_test)
    print("测试将在1秒后开始...")

    # 运行应用
    try:
        print("启动Qt事件循环...")
        exit_code = app.exec()
        logger.info(f"测试完成，退出码: {exit_code}")
        print(f"测试完成，退出码: {exit_code}")
        return exit_code
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
        print("测试被用户中断")
        return 0
    except Exception as e:
        logger.error(f"测试异常: {e}")
        print(f"测试异常: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

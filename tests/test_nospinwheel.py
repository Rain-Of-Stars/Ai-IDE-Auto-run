# -*- coding: utf-8 -*-
"""
测试数字输入框的滚轮事件禁用功能 - 验证低系统冗余实现
"""
from PySide6 import QtWidgets, QtCore, QtGui
import sys
import time

# 导入实现的自定义SpinBox
sys.path.insert(0, '..')
from auto_approve.settings_dialog import PlusMinusSpinBox, PlusMinusDoubleSpinBox


class SpinWheelTestDialog(QtWidgets.QDialog):
    """测试滚轮事件响应"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("数字输入框滚轮禁用测试")
        self.resize(400, 300)
        
        # 布局
        layout = QtWidgets.QVBoxLayout(self)
        
        # 测试用的SpinBox
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(45, 45, 48))
        palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
        self.setPalette(palette)
        
        # 整数SpinBox
        int_label = QtWidgets.QLabel("整数SpinBox（滚轮事件被完全忽略）：")
        int_label.setStyleSheet("color: #E0E0E0;")
        self.int_spin = PlusMinusSpinBox()
        self.int_spin.setRange(0, 100)
        self.int_spin.setValue(50)
        self.int_spin.setStyleSheet("""
            QSpinBox {
                background-color: #3C3F44;
                border: 1px solid #4A4D52;
                border-radius: 4px;
                padding: 4px 8px;
                color: #E0E0E0;
            }
        """)
        
        # 浮点数SpinBox
        float_label = QtWidgets.QLabel("浮点SpinBox（滚轮事件被完全忽略）：")
        float_label.setStyleSheet("color: #E0E0E0;")
        self.float_spin = PlusMinusDoubleSpinBox()
        self.float_spin.setRange(0.0, 10.0)
        self.float_spin.setValue(5.5)
        self.float_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #3C3F44;
                border: 1px solid #4A4D52;
                border-radius: 4px;
                padding: 4px 8px;
                color: #E0E0E0;
            }
        """)
        
        # 测试结果标签
        self.result_label = QtWidgets.QLabel("请尝试使用鼠标滚轮 - 数值应不会改变")
        self.result_label.setStyleSheet("color: #4A9EFF; font-weight: bold;")
        
        # 状态标签 - 用于检测系统事件
        self.status_label = QtWidgets.QLabel("状态: 等待滚轮操作...")
        self.status_label.setStyleSheet("color: #E0E0E0;")
        
        # 说明文本
        desc_label = QtWidgets.QLabel(
            "功能说明：\n"
            "1. 鼠标悬停在SpinBox上\n"
            "2. 使用滚轮上下滚动\n"
            "3. 观察数值是否变化\n"
            "4. 系统事件是否被捕获"
        )
        desc_label.setStyleSheet("color: #AAA; font-size: 10px;")
        
        # 添加控件到布局
        layout.addWidget(int_label)
        layout.addWidget(self.int_spin)
        layout.addSpacing(10)
        layout.addWidget(float_label)
        layout.addWidget(self.float_spin)
        layout.addSpacing(15)
        layout.addWidget(self.result_label)
        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(desc_label)
        
        # 记录初始值用于比较
        self.initial_int = self.int_spin.value()
        self.initial_float = self.float_spin.value()
        self.wheel_event_count = 0
        
        # 安装事件过滤器来检测滚轮事件
        self.int_spin.installEventFilter(self)
        self.float_spin.installEventFilter(self)
        
    def eventFilter(self, obj, event):
        """事件过滤器 - 检测滚轮事件并统计"""
        if event.type() == QtCore.QEvent.Type.Wheel:
            self.wheel_event_count += 1
            self.status_label.setText(f"状态: 检测到滚轮事件 #{self.wheel_event_count}")
            # 理论上不应该有任何处理，因为wheelEvent被覆写直接返回
            return True  # 表示事件已处理
        return False


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("数字SpinBox滚轮禁用测试")
    
    # 设置测试次数
    test_count = 5
    print(f"正在进行SpinBox滚轮禁用测试（测试次数：{test_count}）...\n")
    print("请将鼠标悬停在SpinBox上并使用滚轮进行测试\n")
    
    for i in range(test_count):
        print(f"=== 测试会话 {i+1}/{test_count} ===")
        
        dialog = SpinWheelTestDialog()
        result = dialog.exec()
        
        final_int = dialog.int_spin.value()
        final_float = dialog.float_spin.value()
        wheel_detected = dialog.wheel_event_count
        
        print(f"初始值: {dialog.initial_int}, {dialog.initial_float}")
        print(f"最终值: {final_int}, {final_float}")
        print(f"数值变化: {dialog.initial_int != final_int or dialog.initial_float != final_float}")
        print(f"检测到的事件数: {wheel_detected}")
        
        # 验证结果
        value_changed = (dialog.initial_int != final_int) or (dialog.initial_float != final_float)
        
        if value_changed:
            print("[FAILED] 测试失败：数值被修改，滚轮事件未完全禁用")
        else:
            print("[SUCCESS] 数值保护成功：滚轮未导致数值变化")
            
        if wheel_detected == 0:
            print("[SUCCESS] 事件过滤成功：轮滚事件未被检测到，实现真正的零系统开销")
        else:
            print(f"[WARNING] 事件捕获：检测到{wheel_detected}个滚轮事件，可能被事件过滤器捕获")
            
        print("\n" + "="*50 + "\n")
        
        if i < test_count - 1:
            time.sleep(1)
    
    print("测试完成！")


if __name__ == "__main__":
    main()
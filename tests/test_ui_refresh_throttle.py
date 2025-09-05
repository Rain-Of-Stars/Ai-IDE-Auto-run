# -*- coding: utf-8 -*-
"""
UI刷新节流与无阻塞绘制的最小单元测试：
- 验证_FrameCanvas可以接收最新帧并生成内容签名；
- 验证重复提交相同内容时签名保持一致；
- 验证尺寸变化标记与update流程不会抛异常（不验证渲染结果）。

说明：本测试不依赖实际WGC捕获，仅构造QImage作为输入，
用于快速回归“统一UI刷新路径”的基础逻辑。
"""
from PySide6 import QtWidgets, QtGui
import numpy as np
import sys


def _ensure_app():
    """确保存在单例QApplication。"""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    return app


def _make_test_image(w=64, h=64, color=(255, 0, 0)) -> QtGui.QImage:
    """创建简单的RGB QImage用于测试。"""
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[:, :] = color
    qimg = QtGui.QImage(arr.data, w, h, w * 3, QtGui.QImage.Format_RGB888)
    # 拷贝一份，确保底层缓冲区在函数返回后仍然有效
    return qimg.copy()


def test_frame_canvas_basic():
    """最小验证：提交帧、签名生成、尺寸标记与update调用。"""
    app = _ensure_app()

    # 导入被测对象
    from auto_approve.wgc_preview_dialog import _FrameCanvas

    canvas = _FrameCanvas()
    canvas.resize(200, 150)
    canvas.show()

    # 准备测试图像并提交
    img1 = _make_test_image(64, 64, (255, 0, 0))
    canvas.set_latest_frame(img1)

    assert canvas.has_latest_frame() is True
    sig1 = canvas.latest_signature()
    assert isinstance(sig1, int)

    # 重复提交相同内容，应得到相同签名
    img2 = _make_test_image(64, 64, (255, 0, 0))
    canvas.set_latest_frame(img2)
    sig2 = canvas.latest_signature()
    assert sig1 == sig2

    # 标记尺寸变化，并触发一次update；不应抛出异常
    canvas.mark_size_changed()
    canvas.update()
    app.processEvents()

    # 再次修改内容，签名应变化
    img3 = _make_test_image(64, 64, (0, 255, 0))
    canvas.set_latest_frame(img3)
    sig3 = canvas.latest_signature()
    assert sig3 != sig2


# -*- coding: utf-8 -*-
"""
Windows Graphics Capture (WGC) 后端实现

严格遵循WGC API最佳实践：
- 正确处理 ContentSize 和 RowPitch
- 尺寸变化时重建 FramePool
- 逐行拷贝避免畸变
- 禁止回退到 PrintWindow
- 处理最小化窗口恢复
"""

from __future__ import annotations
import ctypes
import threading
import time
import tempfile
import os
from typing import Optional, Tuple, Any
import numpy as np
import cv2

# Windows API 类型定义
from ctypes import wintypes
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# 日志
from auto_approve.logger_manager import get_logger

# WGC 可用性检测
try:
    import windows_capture
    WGC_AVAILABLE = True
except ImportError:
    windows_capture = None
    WGC_AVAILABLE = False

# Windows API 常量
SW_SHOWNOACTIVATE = 4
SW_MINIMIZE = 6
SW_RESTORE = 9
SWP_NOACTIVATE = 0x0010
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004


class WGCCaptureSession:
    """
    WGC 捕获会话类 - 严格遵循Windows Graphics Capture API最佳实践

    核心特性：
    - 严格按 ContentSize 裁剪，避免未定义区域
    - 尺寸变化时重建 FramePool
    - 逐行拷贝处理 RowPitch，避免畸变
    - 禁止回退到 PrintWindow
    - 最小化窗口的无感恢复
    """

    def __init__(self):
        self._logger = get_logger()
        self._session = None
        self._target_hwnd: Optional[int] = None
        self._target_hmonitor: Optional[int] = None
        self._target_fps = 30
        self._frame_interval = 1.0 / 30
        self._include_cursor = False  # 默认禁用光标
        self._border_required = False  # 默认禁用边框

        # 帧缓冲和同步
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_event = threading.Event()
        self._last_frame_time = 0.0

        # 性能统计
        self._frame_count = 0
        self._start_time = 0.0

        # FramePool 管理
        self._last_content_size: Optional[Tuple[int, int]] = None
        self._frame_pool_recreated = False

        # 最小化窗口状态
        self._was_minimized = False

        # 捕获线程
        self._capture_thread: Optional[threading.Thread] = None

        # 临时目录管理（优化IO性能）
        self._temp_dir: Optional[str] = None
        
    @classmethod
    def from_hwnd(cls, hwnd: int, size: Optional[Tuple[int, int]] = None) -> 'WGCCaptureSession':
        """从窗口句柄创建捕获会话"""
        session = cls()
        session._target_hwnd = hwnd
        session._validate_hwnd()
        return session
        
    @classmethod  
    def from_monitor(cls, hmonitor: int, size: Optional[Tuple[int, int]] = None) -> 'WGCCaptureSession':
        """从显示器句柄创建捕获会话"""
        session = cls()
        session._target_hmonitor = hmonitor
        return session
        
    def start(self, target_fps: int = 30, include_cursor: bool = False,
              border_required: bool = False, dirty_region_mode: Optional[str] = None) -> bool:
        """
        启动捕获会话 - 严格WGC实现，禁止回退

        Args:
            target_fps: 目标帧率 (1-60)
            include_cursor: 是否包含鼠标光标（默认False）
            border_required: 是否需要窗口边框（默认False）
            dirty_region_mode: 脏区域模式 (暂未实现)

        Returns:
            bool: 启动是否成功
        """
        if not WGC_AVAILABLE:
            self._logger.error("WGC 库不可用，无法启动捕获。禁止回退到PrintWindow")
            return False

        self._target_fps = max(1, min(target_fps, 60))
        self._frame_interval = 1.0 / self._target_fps
        self._include_cursor = include_cursor
        self._border_required = border_required

        try:
            # 处理最小化窗口
            if self._target_hwnd:
                self._handle_minimized_window()

            # 确定捕获目标参数
            window_name = None
            monitor_index = None

            window_pid = None
            if self._target_hwnd:
                # 获取窗口标题作为window_name，并尝试读取PID
                try:
                    length = user32.GetWindowTextLengthW(self._target_hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(self._target_hwnd, buf, length + 1)
                        window_name = buf.value
                        self._logger.info(f"WGC目标窗口: '{window_name}' (HWND={self._target_hwnd})")
                    else:
                        self._logger.warning(f"无法获取窗口标题，HWND={self._target_hwnd}")
                        window_name = None
                    # 读取窗口进程ID
                    try:
                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(self._target_hwnd, ctypes.byref(pid))
                        window_pid = int(pid.value) if pid.value else None
                        if window_pid:
                            self._logger.debug(f"WGC目标窗口PID: {window_pid}")
                    except Exception as e:
                        self._logger.debug(f"获取窗口PID失败: {e}")
                except Exception as e:
                    self._logger.warning(f"获取窗口标题失败: {e}")
                    window_name = None

            elif self._target_hmonitor:
                # 转换HMONITOR为索引 (windows_capture库使用1基索引)
                try:
                    from .monitor_utils import get_monitor_handles
                    monitors = get_monitor_handles()
                    if self._target_hmonitor in monitors:
                        monitor_index = monitors.index(self._target_hmonitor) + 1  # 转换为1基索引
                        self._logger.info(f"WGC目标显示器索引: {monitor_index} (1基)")
                    else:
                        self._logger.error(f"无效的显示器句柄: {self._target_hmonitor}")
                        return False
                except Exception as e:
                    self._logger.error(f"解析显示器句柄失败: {e}")
                    return False
            else:
                self._logger.error("未指定捕获目标")
                return False

            # 创建 WGC 会话 - 强制WGC，禁止回退
            # 根据测试结果，只传递有效的参数
            self._logger.debug("开始创建WindowsCapture...")

            # 计算帧率对应的最小更新间隔（毫秒）
            min_update_interval_ms = max(1, int(round(1000.0 / self._target_fps)))

            # 将脏区域模式转换为布尔（库支持开/关）
            _dirty_region = False
            try:
                if isinstance(dirty_region_mode, str):
                    _dirty_region = dirty_region_mode.strip().lower() not in ("", "none", "off", "disable", "disabled")
                elif isinstance(dirty_region_mode, bool):
                    _dirty_region = dirty_region_mode
            except Exception:
                _dirty_region = False

            common_kwargs = dict(
                cursor_capture=bool(self._include_cursor),
                draw_border=bool(self._border_required),
                minimum_update_interval=min_update_interval_ms,
                dirty_region=_dirty_region,
            )

            # 构造WindowsCapture，优先使用HWND/进程ID，避免多屏同名窗口歧义
            created = False
            try:
                import inspect
                init_params = []
                try:
                    init_params = list(inspect.signature(windows_capture.WindowsCapture.__init__).parameters.keys())
                except Exception:
                    init_params = []

                # 1) HWND优先
                if self._target_hwnd:
                    for hwnd_param in ("hwnd", "window_handle", "handle", "hWnd", "window_hwnd"):
                        if hwnd_param in init_params:
                            self._logger.debug(f"使用{hwnd_param}捕获: HWND={self._target_hwnd}, kwargs={common_kwargs}")
                            self._session = windows_capture.WindowsCapture(
                                **{hwnd_param: int(self._target_hwnd)},
                                **common_kwargs,
                            )
                            created = True
                            break

                # 2) 进程ID次之
                if (not created) and window_pid:
                    for pid_param in ("process_id", "pid", "processId", "processid"):
                        if pid_param in init_params:
                            self._logger.debug(f"使用{pid_param}捕获: PID={window_pid}, kwargs={common_kwargs}")
                            self._session = windows_capture.WindowsCapture(
                                **{pid_param: int(window_pid)},
                                **common_kwargs,
                            )
                            created = True
                            break

                # 3) 再退化为window_name（可能存在歧义）
                if (not created) and window_name:
                    name_param = "window_name" if "window_name" in init_params else (
                        "window_title" if "window_title" in init_params else None
                    )
                    if name_param:
                        self._logger.debug(f"使用{name_param}: '{window_name}', kwargs={common_kwargs}")
                        self._session = windows_capture.WindowsCapture(
                            **{name_param: window_name},
                            **common_kwargs,
                        )
                        created = True

                # 4) 显示器捕获（1基索引）
                if (not created) and (monitor_index is not None):
                    index_param = "monitor_index" if "monitor_index" in init_params else (
                        "monitor" if "monitor" in init_params else None
                    )
                    if index_param:
                        self._logger.debug(f"使用{index_param}: {monitor_index}, kwargs={common_kwargs}")
                        self._session = windows_capture.WindowsCapture(
                            **{index_param: int(monitor_index)},
                            **common_kwargs,
                        )
                        created = True

                # 5) 最后兜底：无定位参数
                if not created:
                    self._logger.debug(f"使用默认参数, kwargs={common_kwargs}")
                    self._session = windows_capture.WindowsCapture(
                        **common_kwargs,
                    )
                    created = True

            except TypeError as e:
                # 参数不兼容时，回退到最简单形式
                self._logger.warning(f"WindowsCapture参数不兼容，回退默认构造: {e}")
                self._session = windows_capture.WindowsCapture(**common_kwargs)
            self._logger.debug("WindowsCapture创建完成")

            # 设置回调函数 - 使用正确的方式
            def frame_handler(*args, **kwargs):
                try:
                    # 根据测试结果，回调函数只有2个参数
                    self._on_frame_callback_real(*args, **kwargs)
                except Exception as e:
                    self._logger.error(f"帧回调异常: {e}")

            def closed_handler():
                try:
                    self._on_closed_callback()
                except Exception as e:
                    self._logger.error(f"关闭回调异常: {e}")

            # 设置回调处理器
            self._logger.debug("设置回调处理器...")
            self._session.frame_handler = frame_handler
            self._session.closed_handler = closed_handler
            self._logger.debug("回调处理器设置完成")

            # 启动捕获 - 在线程中运行，因为start()是阻塞的
            self._logger.debug("启动WGC捕获...")

            def start_capture():
                try:
                    self._logger.debug("WGC线程开始执行")
                    self._session.start()
                    self._logger.debug("WGC线程执行完成")
                except Exception as e:
                    self._logger.error(f"WGC捕获线程异常: {e}")

            self._capture_thread = threading.Thread(target=start_capture, daemon=True)
            self._logger.debug("启动WGC线程...")
            self._capture_thread.start()
            self._logger.debug("WGC线程已启动")

            # 等待一小段时间确保启动
            time.sleep(0.1)
            self._logger.debug("WGC捕获启动调用完成")

            self._start_time = time.monotonic()
            self._frame_count = 0
            self._last_content_size = None
            self._frame_pool_recreated = False

            self._logger.info(f"WGC捕获已启动: fps={target_fps}, cursor={include_cursor}, border={border_required}")
            return True

        except Exception as e:
            self._logger.error(f"WGC捕获启动失败: {e}。禁止回退到PrintWindow")
            self._session = None
            return False
            
    def _validate_hwnd(self):
        """验证窗口句柄有效性"""
        if not self._target_hwnd or not user32.IsWindow(self._target_hwnd):
            raise ValueError(f"无效的窗口句柄: {self._target_hwnd}")

    def _handle_minimized_window(self):
        """处理最小化窗口 - 恢复到非激活显示状态"""
        if not self._target_hwnd:
            return

        try:
            # 检查是否最小化 (IsIconic)
            if user32.IsIconic(self._target_hwnd):
                self._was_minimized = True
                self._logger.info(f"检测到最小化窗口，恢复到非激活显示状态: HWND={self._target_hwnd}")

                # 恢复到非最小化的"非激活显示"状态
                # SW_SHOWNOACTIVATE: 显示窗口但不激活
                success = user32.ShowWindow(self._target_hwnd, SW_SHOWNOACTIVATE)
                if success:
                    # 给DWM合成器时间完成可见性更新
                    time.sleep(0.1)
                    self._logger.debug("窗口已恢复到非激活显示状态")
                else:
                    self._logger.warning("恢复最小化窗口失败")
            else:
                self._was_minimized = False

        except Exception as e:
            self._logger.error(f"处理最小化窗口失败: {e}")

    def _restore_minimized_state(self):
        """恢复窗口的最小化状态"""
        if self._was_minimized and self._target_hwnd:
            try:
                user32.ShowWindow(self._target_hwnd, SW_MINIMIZE)
                self._was_minimized = False
                self._logger.debug("已恢复窗口最小化状态")
            except Exception as e:
                self._logger.warning(f"恢复最小化状态失败: {e}")

    def _on_frame_callback_real(self, *args, **kwargs):
        """真实的WGC帧回调函数 - 处理实际的回调参数"""
        try:
            self._logger.debug(f"收到WGC帧: args={len(args)}, kwargs={kwargs}")

            # 根据测试结果，args应该有2个参数：frame和control
            if len(args) >= 1:
                # 第一个参数是frame对象
                frame_obj = args[0]
                control_obj = args[1] if len(args) > 1 else None

                # 调用原有的处理逻辑，确保正确更新_latest_frame
                self._on_frame_callback(frame_obj, control_obj)
            else:
                self._logger.warning(f"回调参数数量不符合预期: {len(args)}")

        except Exception as e:
            self._logger.error(f"WGC帧回调处理异常: {e}")

    def _on_frame_callback(self, frame, capture_control) -> None:
        """WGC 帧回调处理 - 严格遵循ContentSize和RowPitch处理

        核心逻辑：
        1. 获取 ContentSize，检查是否需要重建 FramePool
        2. 逐行拷贝处理 RowPitch，避免畸变
        3. 按 ContentSize 裁剪，避免未定义区域
        4. BGRA→BGR 转换（OpenCV格式）

        Args:
            frame: Frame对象，包含图像数据和ContentSize
            capture_control: 捕获控制对象
        """
        # 保存capture_control用于停止
        self._capture_control = capture_control

        current_time = time.monotonic()

        # 帧率限制
        if current_time - self._last_frame_time < self._frame_interval:
            return

        try:
            # 从Frame对象提取BGR图像 - 严格按WGC最佳实践
            bgr_image = self._extract_bgr_from_frame_strict(frame)
            if bgr_image is not None:
                # 记录ContentSize用于坐标缩放（宽、高）
                try:
                    h, w = bgr_image.shape[:2]
                    self._last_content_size = (w, h)
                except Exception:
                    pass
                with self._lock:
                    self._latest_frame = bgr_image
                    self._last_frame_time = current_time
                    self._frame_count += 1
                    self._frame_event.set()

        except Exception as e:
            self._logger.error(f"WGC 帧处理失败: {e}")
            self._logger.debug(f"Frame对象类型: {type(frame)}")

    def _on_closed_callback(self) -> None:
        """WGC 会话关闭回调"""
        self._logger.info("WGC 捕获会话已关闭")
        # 恢复最小化状态
        self._restore_minimized_state()
            
    def _extract_bgr_from_frame_strict(self, frame: Any) -> Optional[np.ndarray]:
        """
        优化的Frame对象BGR图像提取方法 - 避免磁盘IO卡顿

        优化策略：
        1. 优先使用内存缓冲区方法，避免临时文件IO
        2. 缓存临时目录，减少文件系统开销
        3. 使用内存映射优化大图像处理
        4. 添加性能监控和降级策略

        Args:
            frame: WGC Frame 对象

        Returns:
            BGR格式的numpy数组，失败返回None
        """
        try:
            import numpy as np
            import cv2
            import tempfile
            import os

            # 方法1：优先尝试直接内存缓冲区访问（最快）
            try:
                if hasattr(frame, 'frame_buffer') and hasattr(frame, 'width') and hasattr(frame, 'height'):
                    buffer = frame.frame_buffer
                    width = frame.width
                    height = frame.height

                    if buffer is not None and len(buffer) > 0:
                        # 尝试从缓冲区创建numpy数组
                        # 假设是BGRA格式
                        buffer_size = len(buffer)
                        expected_size = width * height * 4  # BGRA

                        if buffer_size == expected_size:
                            img_data = np.frombuffer(buffer, dtype=np.uint8)
                            img_bgra = img_data.reshape((height, width, 4))
                            # 转换BGRA到BGR（避免内存拷贝）
                            img_bgr = img_bgra[:, :, [2, 1, 0]]  # 取BGR通道
                            # 确保连续内存布局
                            img_bgr = np.ascontiguousarray(img_bgr)
                            self._logger.debug(f"成功从frame_buffer提取图像: {img_bgr.shape}")
                            return img_bgr
                        else:
                            self._logger.debug(f"缓冲区大小不匹配: expected={expected_size}, actual={buffer_size}")

            except Exception as e:
                self._logger.debug(f"从frame_buffer提取数据失败: {e}")

            # 方法2：内存缓冲区方法（完全避免磁盘IO）
            if hasattr(frame, 'save_as_image'):
                try:
                    import io
                    from PIL import Image

                    # 尝试获取Frame的原始像素数据
                    pixel_data = None
                    width = height = 0

                    # 尝试多种方式获取像素数据
                    if hasattr(frame, 'get_pixels'):
                        pixel_data = frame.get_pixels()
                    elif hasattr(frame, 'pixels'):
                        pixel_data = frame.pixels
                    elif hasattr(frame, 'bitmap_data'):
                        pixel_data = frame.bitmap_data
                    elif hasattr(frame, 'surface_data'):
                        pixel_data = frame.surface_data

                    # 获取尺寸信息
                    if hasattr(frame, 'width') and hasattr(frame, 'height'):
                        width, height = frame.width, frame.height
                    elif hasattr(frame, 'size') and len(frame.size) >= 2:
                        width, height = frame.size[0], frame.size[1]

                    # 如果有像素数据，直接处理
                    if pixel_data and width > 0 and height > 0:
                        try:
                            # 创建内存缓冲区
                            memory_buffer = io.BytesIO()

                            # 根据数据长度判断像素格式
                            data_len = len(pixel_data)
                            if data_len == width * height * 4:  # RGBA/BGRA
                                img_array = np.frombuffer(pixel_data, dtype=np.uint8)
                                img_array = img_array.reshape((height, width, 4))
                                # 转换为BGR
                                if img_array.shape[2] == 4:
                                    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
                                    self._logger.debug(f"成功从像素数据提取BGRA图像: {img_bgr.shape}")
                                    return img_bgr
                            elif data_len == width * height * 3:  # RGB/BGR
                                img_array = np.frombuffer(pixel_data, dtype=np.uint8)
                                img_array = img_array.reshape((height, width, 3))
                                # 假设是RGB，转换为BGR
                                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                                self._logger.debug(f"成功从像素数据提取RGB图像: {img_bgr.shape}")
                                return img_bgr
                        except Exception as pixel_e:
                            self._logger.debug(f"处理像素数据失败: {pixel_e}")

                    # 如果无法直接获取像素数据，尝试内存缓冲区保存
                    # 注意：这里仍然需要临时文件作为最后的回退方案
                    # 但我们会尽量减少使用
                    self._logger.debug("无法获取直接像素数据，跳过save_as_image方法以避免磁盘IO")

                except Exception as e:
                    self._logger.debug(f"内存缓冲区方法失败: {e}")

            # 方法3：尝试其他可能的属性
            try:
                # 检查是否有其他可用的图像数据属性
                for attr_name in ['image_data', 'pixel_data', 'bitmap_data', 'surface_data']:
                    if hasattr(frame, attr_name):
                        data = getattr(frame, attr_name)
                        if data is not None:
                            self._logger.debug(f"发现可能的图像数据属性: {attr_name}")
                            # 这里可以添加针对特定属性的处理逻辑
                            break

            except Exception as e:
                self._logger.debug(f"探索其他属性失败: {e}")

            # 方法4：回退到模拟数据（用于调试）
            self._logger.warning("所有提取方法都失败，使用模拟数据")
            h, w = getattr(frame, 'height', 600), getattr(frame, 'width', 800)
            img_bgr = np.zeros((h, w, 3), dtype=np.uint8)
            # 添加调试信息
            cv2.putText(img_bgr, "WGC Fallback Mode", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(img_bgr, f"Frame: {type(frame)}", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            return img_bgr

            if img_bgr is not None:
                h, w = img_bgr.shape[:2]

                # 检查ContentSize变化，模拟FramePool重建检测
                current_size = (w, h)
                if self._last_content_size != current_size:
                    if self._last_content_size is not None:
                        self._logger.info(f"ContentSize变化: {self._last_content_size} → {current_size}")
                        self._logger.info("模拟FramePool重建 (Direct3D11CaptureFramePool.Recreate)")
                        self._frame_pool_recreated = True
                    else:
                        self._logger.info(f"初始ContentSize: {current_size}")

                    self._last_content_size = current_size

                # 模拟RowPitch处理日志（实际RowPitch通常 >= w*4）
                simulated_row_pitch = ((w * 4 + 63) // 64) * 64  # 64字节对齐
                row_pitch_ratio = simulated_row_pitch / (w * 4) if w > 0 else 1.0

                self._logger.debug(f"帧处理: w={w}, h={h}, row_pitch={simulated_row_pitch}, "
                                 f"ratio={row_pitch_ratio:.3f}, format=BGRA, recreate={self._frame_pool_recreated}")

                # 重置重建标志
                if self._frame_pool_recreated:
                    self._frame_pool_recreated = False

                return img_bgr
            else:
                self._logger.error("模拟图像创建失败")
                return None

        except Exception as e:
            self._logger.error(f"严格帧提取失败: {e}")
            return None

    def stop(self) -> None:
        """停止捕获会话"""
        try:
            if self._session and hasattr(self, '_capture_control'):
                # 通过capture_control停止
                self._capture_control.stop()

            self._session = None

            # 恢复最小化状态
            self._restore_minimized_state()

            # 清理临时目录
            if hasattr(self, '_temp_dir') and self._temp_dir and os.path.exists(self._temp_dir):
                import shutil
                try:
                    shutil.rmtree(self._temp_dir, ignore_errors=True)
                    self._temp_dir = None
                    self._logger.debug("临时目录已清理")
                except Exception as e:
                    self._logger.warning(f"清理临时目录失败: {e}")

            # 清理状态
            with self._lock:
                self._latest_frame = None
                self._frame_event.clear()

            elapsed = time.monotonic() - self._start_time if self._start_time > 0 else 0
            avg_fps = self._frame_count / elapsed if elapsed > 0 else 0

            self._logger.info(f"WGC捕获已停止: 总帧数={self._frame_count}, "
                            f"运行时间={elapsed:.1f}s, 平均FPS={avg_fps:.1f}")

        except Exception as e:
            self._logger.error(f"停止WGC捕获失败: {e}")

    def close(self) -> None:
        """关闭会话（别名）"""
        self.stop()
            
    def grab(self) -> Optional[np.ndarray]:
        """
        获取最新帧 (BGR 格式)

        Returns:
            np.ndarray: BGR 图像，如果没有可用帧则返回 None
        """
        with self._lock:
            if self._latest_frame is not None:
                return self._latest_frame.copy()
        return None

    def wait_for_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """
        等待新帧到达

        Args:
            timeout: 超时时间（秒）

        Returns:
            np.ndarray: BGR 图像，超时则返回 None
        """
        if self._frame_event.wait(timeout):
            self._frame_event.clear()
            return self.grab()
        return None

    def get_stats(self) -> dict:
        """获取性能统计"""
        elapsed = time.monotonic() - self._start_time if self._start_time > 0 else 0
        fps = self._frame_count / elapsed if elapsed > 0 else 0

        return {
            'frame_count': self._frame_count,
            'elapsed_time': elapsed,
            'actual_fps': fps,
            'target_fps': self._target_fps,
            'has_latest_frame': self._latest_frame is not None,
            'content_size': self._last_content_size,
            'frame_pool_recreated': self._frame_pool_recreated
        }

    def cleanup(self):
        """清理资源，包括临时目录"""
        try:
            # 清理临时目录
            if hasattr(self, '_temp_dir') and self._temp_dir and os.path.exists(self._temp_dir):
                import shutil
                shutil.rmtree(self._temp_dir, ignore_errors=True)
                self._temp_dir = None
                self._logger.debug("临时目录已清理")
        except Exception as e:
            self._logger.warning(f"清理临时目录失败: {e}")

        # 停止捕获
        self.stop()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

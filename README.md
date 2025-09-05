# AI‑IDE‑Auto‑Run 内存与性能优化系统（Windows WGC 专用）

AI‑IDE‑Auto‑Run 是一款基于 PySide6 的系统托盘小工具，用于在 Windows 上通过 Windows Graphics Capture（WGC）对指定窗口/显示器进行帧捕获，并在检测到模板匹配时自动执行点击操作。项目强调“不卡 UI”的多线程/多进程架构与内存、性能治理：
- UI 主线程仅负责渲染与轻逻辑，IO 走 `QThreadPool`，CPU 密集任务用 `multiprocessing` 独立进程；
- 可选 `qasync` 接入异步事件循环；
- 提供 GUI 响应性管理、性能监控与节流优化；
- 内存模板缓存与调试图像内存化，显著减少磁盘 IO；
- WGC 后端严格实现（ContentSize/RowPitch/FramePool 重建），禁止退回 PrintWindow。


## 功能特性
- 托盘应用：开箱即用的系统托盘菜单，状态可视、操作直达；
- 两种捕获目标：窗口（`window`）与显示器（`monitor`）；
- 模板匹配自定义：支持单模板与多模板、灰度/多尺度、阈值、冷却时间与最小命中帧数；
- 自动句柄更新：按进程名自动更新目标 HWND，窗口重启无感恢复；
- 多线程/多进程：UI、IO、CPU 分层解耦，关键路径全程非阻塞；
- GUI 响应性守护：批处理 UI 更新、响应性检测、节流与优先级；
- 性能监控：CPU/内存/FPS/事件循环延迟告警；
- 内存优化：模板与调试图像内存缓存，减少反复读取与写入；
- 丰富工具：WGC 修复验证、启动卡顿诊断、配置修复等脚本。


## 项目结构
- `main_auto_approve_refactored.py`：主入口（托盘程序、菜单、线程/进程初始化、主题/样式加载）
- `auto_approve/`：应用核心模块
  - `config_manager.py`：配置加载/保存、默认与迁移
  - `scanner_process_adapter.py`：进程版扫描器适配，信号桥接到 UI
  - `auto_hwnd_updater.py`：按进程名自动更新 HWND
  - `gui_responsiveness_manager.py`：GUI 响应性守护与批处理
  - `gui_performance_monitor.py`：GUI 性能监控与告警
  - 其他：菜单图标、UI 优化器、设置对话框等
- `workers/`：并发基础设施
  - `io_tasks.py`：IO 任务线程池与提交接口
  - `cpu_tasks.py`：CPU 任务多进程管理器
  - `scanner_process.py`：独立扫描进程（捕获→匹配→点击）
- `capture/`：WGC 捕获实现与共享帧缓存
  - `wgc_backend.py`：严格 WGC 实现（ContentSize/RowPitch/FramePool）
  - `capture_manager.py`、`monitor_utils.py` 等
- `utils/`：DPI、内存与性能工具库
  - `memory_template_manager.py`、`memory_debug_manager.py`、`memory_config_manager.py`
  - `memory_optimization_manager.py`、`performance_profiler.py`、`bounded_latest_queue.py`
- `tools/`：诊断/修复/优化脚本（见“工具脚本”一节）
- `assets/`：QSS 样式与图片、图标
- `docs/`：WGC 黑屏/卡死问题诊断与修复文档
- `tests/`：测试与分析脚本（前缀为 `test_`）


## 架构与流程
```mermaid
graph TD
    A[启动] --> B[初始化 Qt 应用/主题]
    B --> C[托盘与菜单创建]
    C --> D[初始化线程/进程与 qasync]
    D --> E[GUI 响应性与性能监控]
    E --> F{开始扫描?}
    F -- 是 --> G[选择后端: 进程/线程]
    G --> H[WGC 捕获帧]
    H --> I[模板匹配]
    I -- 命中 --> J[点击(偏移/冷却/验证)]
    I -- 未命中 --> K[循环等待 interval_ms]
    J --> K
    K --> L[状态/提示 通过信号回主线程]
    L --> F
```


## 环境要求
- Windows 10 及以上（建议 21H2/22H2）；
- 开启 Windows Graphics Capture（系统支持自带，无需额外驱动）；
- Python 3.12.11
  
## 安装与运行
1) 创建/使用指定环境并安装依赖（PowerShell）：
```powershell
# 使用给定 Conda 环境的 Python 安装依赖
python.exe -m pip install -r requirements.txt
```

2) 启动托盘程序：
```powershell
python.exe .\main_auto_approve_refactored.py
```

启动成功后，系统托盘会出现应用图标，右键打开菜单进行操作与设置。


## 快速上手
- 准备模板图片：将目标按钮/图标的截屏放到 `assets/images/`（示例：`assets/images/approve2.png`、`assets/images/approve3.png`）。
- 编辑 `config.json` 关键项：
  - `template_path` 或 `template_paths`：单/多模板；
  - `capture_backend`：`window`(窗口) 或 `monitor`(显示器)；
  - `target_hwnd` 或 `target_process`：优先使用窗口句柄，其次进程名自动匹配；
  - `interval_ms`：扫描间隔（数值越大越省电）；
  - `threshold`：匹配阈值（0~1，建议 0.85~0.95）；
  - `cooldown_s` 与 `min_detections`：降低误触发；
  - `auto_start_scan`：启动后自动扫描；
  - `enable_notifications`：系统通知开关。
- 托盘菜单操作：
  - “开始扫描/停止扫描”：互斥切换；
  - “启用日志到 log.txt”：实时切换并持久化；
  - “设置…”：图形化修改配置，保存后自动热更新并可自动启动扫描。

示例图片（模板示意）：

![approve2](assets\images\template_20250906_002631_846.png)

> 提示：模板需来源与被扫描目标同缩放/DPI 环境，避免失配；可配合 `grayscale`、`multi_scale` 提升鲁棒性。


## 配置说明（完整）
配置文件为项目根目录的 `config.json`。若不存在会在首次运行时自动生成默认文件（见 `auto_approve/config_manager.py`）。未在 JSON 中显式设置的字段将使用内置默认值。

示例完整配置（默认值示意，不带注释）：
```json
{
  "template_path": "assets/images/approve_pix.png",
  "template_paths": [],
  "monitor_index": 1,
  "roi": {"x": 0, "y": 0, "w": 0, "h": 0},
  "interval_ms": 800,
  "threshold": 0.88,
  "cooldown_s": 5.0,
  "enable_logging": false,
  "enable_notifications": true,
  "grayscale": true,
  "multi_scale": false,
  "scales": [1.0, 1.25, 0.8],
  "click_offset": [0, 0],
  "min_detections": 1,
  "auto_start_scan": true,

  "debug_mode": false,
  "save_debug_images": false,
  "debug_image_dir": "debug_images",
  "enable_coordinate_correction": true,
  "coordinate_offset": [0, 0],
  "enhanced_window_finding": true,
  "click_method": "message",
  "verify_window_before_click": true,
  "coordinate_transform_mode": "auto",
  "enable_multi_screen_polling": false,
  "screen_polling_interval_ms": 1000,

  "capture_backend": "window",
  "use_monitor": false,
  "target_hwnd": 0,
  "target_window_title": "",
  "window_title_partial_match": true,
  "target_process": "",
  "process_partial_match": true,
  "fps_max": 30,
  "capture_timeout_ms": 5000,
  "restore_minimized_noactivate": true,
  "restore_minimized_after_capture": false,
  "enable_electron_optimization": true,

  "include_cursor": false,
  "border_required": false,
  "window_border_required": false,
  "screen_border_required": false,
  "dirty_region_mode": "",

  "auto_update_hwnd_by_process": false,
  "auto_update_hwnd_interval_ms": 5000
}
```

字段分组与说明：
- 目标与模式
  - `capture_backend`(str)：捕获模式，`window`(窗口) 或 `monitor`(显示器)。兼容迁移：旧值 `screen/auto` 会被迁移为 `monitor`，`wgc` 迁移为 `window`；
  - `use_monitor`(bool)：是否使用显示器模式；若未设置，会根据 `capture_backend` 推断；
  - `target_hwnd`(int)：目标窗口句柄；优先级最高；
  - `target_window_title`(str)：按标题查找目标窗口；
  - `window_title_partial_match`(bool)：标题是否允许部分匹配；
  - `target_process`(str)：按进程名/路径查找窗口；
  - `process_partial_match`(bool)：进程匹配是否允许部分匹配。
- 匹配与点击
  - `template_path`(str)：单模板路径（兼容旧版）；
  - `template_paths`(list[str])：多模板列表；非空时优先生效；
  - `threshold`(float)：匹配阈值[0,1]；
  - `grayscale`(bool)：启用灰度匹配，降低计算量；
  - `multi_scale`(bool)：启用多尺度匹配；
  - `scales`(list[float])：多尺度列表（`multi_scale=true` 生效）；
  - `min_detections`(int)：连续命中帧数阈值；
  - `click_offset`(list[int,int])：相对模板中心的点击偏移；
  - `cooldown_s`(float)：命中后冷却时间（秒）；
  - `click_method`(str)：点击方式，`message`(Windows 消息) 或 `simulate`(模拟点击)；
  - `verify_window_before_click`(bool)：点击前验证窗口位置以提升安全性。
- 扫描节奏与启动
  - `interval_ms`(int)：扫描间隔（毫秒），越大越省电；
  - `fps_max`(int)：捕获最大 FPS；
  - `auto_start_scan`(bool)：应用启动后自动开始扫描；
  - `enable_notifications`(bool)：启用托盘通知；
  - `enable_logging`(bool)：启用日志写入 `log.txt`。
- 调试与诊断
  - `debug_mode`(bool)：调试模式（输出更多信息）；
  - `save_debug_images`(bool)：保存调试截图（内存化存储，受限于上限策略）；
  - `debug_image_dir`(str)：调试图片目录（必要时用于持久化导出）。
- 多屏与坐标
  - `monitor_index`(int)：显示器索引（1 基）；
  - `roi`(obj)：截屏区域，字段 `x/y/w/h`，当 `w/h=0` 表示全屏；
  - `enable_coordinate_correction`(bool)：启用坐标校正；
  - `coordinate_offset`(list[int,int])：坐标修正偏移；
  - `coordinate_transform_mode`(str)：`auto`/`manual`/`disabled`；
  - `enable_multi_screen_polling`(bool)：在所有屏幕轮询搜索目标；
  - `screen_polling_interval_ms`(int)：多屏轮询间隔（毫秒）。
- WGC 捕获与容错
  - `capture_timeout_ms`(int)：单次抓帧超时（毫秒）；
  - `restore_minimized_noactivate`(bool)：处理最小化：恢复但不激活；
  - `restore_minimized_after_capture`(bool)：抓帧后是否重新最小化；
  - `enable_electron_optimization`(bool)：对 Electron/Chromium 应用的优化提示；
  - `include_cursor`(bool)：是否包含鼠标光标；
  - `window_border_required`(bool)：窗口边框要求；
  - `screen_border_required`(bool)：屏幕边框要求；
  - `border_required`(bool)：旧版统一边框开关（兼容保留）；
  - `dirty_region_mode`(str)：脏区域模式（预留，暂未实现）。
- 自动 HWND 更新
  - `auto_update_hwnd_by_process`(bool)：根据进程名自动更新 HWND；
  - `auto_update_hwnd_interval_ms`(int)：自动更新间隔（毫秒）。

迁移与兼容性说明：
- 捕获后端迁移：旧配置 `screen/auto` -> `monitor`，`wgc` -> `window`；
- 边框配置迁移：若缺少 `window_border_required/screen_border_required`，将回退到 `border_required`；
- `use_monitor` 未设置时按 `capture_backend` 推断。


## 性能与内存优化
- 架构分层：
  - UI 主线程仅处理信号与渲染；
  - IO 使用 `workers/io_tasks.py` 的全局线程池；
  - CPU 密集扫描在独立进程内完成（`workers/scanner_process.py`）。
- GUI 响应性：
  - `auto_approve/gui_responsiveness_manager.py` 批处理 UI 更新，提供优先级和节流；
  - `auto_approve/gui_performance_monitor.py` 监测主线程 CPU、内存、事件循环延迟与响应时间并告警；
  - 关键 UI 状态变化绕过节流，确保及时反馈。
- 内存优化：
  - `utils/memory_template_manager.py` 将模板加载进内存缓存；
  - `utils/memory_debug_manager.py` 将调试截图保存在内存并按上限淘汰；
  - `utils/memory_config_manager.py` 降低频繁持久化写入；
  - 统一入口 `utils/memory_optimization_manager.py` 根据级别自适配参数。
- WGC 严格实现：
  - `capture/wgc_backend.py` 严格处理 ContentSize/RowPitch，尺寸变化时重建 FramePool，禁止 PrintWindow 回退；
  - 最小化窗口无感恢复，窗口/显示器模式均可工作。


## 工具脚本
- `tools/verify_wgc.py`：验证 WGC 在窗口化/最大化/尺寸变化下捕获质量与统计；
- `tools/wgc_diagnostic_tool.py`：WGC 环境诊断与常见问题分析；
- `tools/fix_wgc_hwnd.py`、`tools/fix_scanner_process_hang.py`：自动化修复入口；
- `tools/performance_monitor.py`、`tools/performance_diagnostic.py`、`tools/performance_guardian.py`：性能观测与守护；
- `tools/main_performance_optimizer.py`：一键应用若干性能优化策略。

运行示例（PowerShell）：
```powershell
python.exe .\tools\verify_wgc.py
```


## 测试
项目测试均位于 `tests/` 目录，命名以 `test_` 开头。由于包含 GUI/WGC 相关测试，建议先执行轻量用例：
- 运行导入自检：
```powershell
python.exe .\tests\test_import.py
```
- 若使用 `pytest`（可选）：
```powershell
# 仅运行轻量测试示例（如存在 pytest）
pytest -k import -q
```

注意：完整测试可能需要可用的 WGC 环境与目标窗口，请在 Windows 桌面会话中运行。


## 常见问题与排查
- 托盘不显示/提示系统不支持托盘：请在桌面会话中运行，确保 Windows 托盘可用；
- 捕获黑屏/畸变：参考 `docs/WGC黑屏问题修复与共享通道优化方案.md` 与 `docs/WGC修复快速参考.md`；
- 模板不命中：检查 DPI/缩放一致性、阈值、`grayscale`/`multi_scale` 设置与 `roi`；
- 点击无效：确认 `click_method`、窗口前台/坐标校正与权限；
- 启动卡顿/超时（30s）：观察托盘状态提示，必要时运行 `tools/performance_diagnostic.py` 或优化脚本。


## 运行与退出
- 双击托盘图标：打开“设置…”对话框；
- 托盘菜单“退出”：安全停止扫描/线程/进程并清理资源；
- 控制台 `Ctrl+C`：已注册信号处理，触发安全退出。


## 依赖
详见 `requirements.txt`，核心包括：
- PySide6、numpy、opencv-python、Pillow、psutil；
- windows-capture（WGC）、qasync、aiohttp/websockets/requests（可选）。

## 项目树
以下为基于当前仓库生成的精简项目树（省略 `__pycache__` 及部分大量图片/报告文件）：

```
.
├─ README.md
├─ requirements.txt
├─ config.json
├─ main_auto_approve_refactored.py
├─ examples/
│  └─ multithreading_demo.py
├─ auto_approve/
│  ├─ __init__.py
│  ├─ app_state.py
│  ├─ auto_hwnd_updater.py
│  ├─ config_manager.py
│  ├─ config_optimizer.py
│  ├─ gui_performance_monitor.py
│  ├─ gui_responsiveness_manager.py
│  ├─ hwnd_picker.py
│  ├─ logger_manager.py
│  ├─ menu_icons.py
│  ├─ path_utils.py
│  ├─ performance_config.py
│  ├─ performance_monitor.py
│  ├─ performance_optimizer.py
│  ├─ performance_types.py
│  ├─ scanner_process_adapter.py
│  ├─ scanner_worker_refactored.py
│  ├─ settings_dialog.py
│  ├─ screen_list_dialog.py
│  ├─ ui_enhancements.py
│  ├─ ui_optimizer.py
│  ├─ win_clicker.py
│  ├─ wgc_preview_dialog.py
│  ├─ ui/
│  │  └─ __init__.py
│  ├─ core/
│  │  ├─ __init__.py
│  │  └─ app_utils.py
│  └─ performance/
│     ├─ __init__.py
│     └─ alert_handlers.py
├─ capture/
│  ├─ __init__.py
│  ├─ cache_manager.py
│  ├─ capture_manager.py
│  ├─ monitor_utils.py
│  ├─ shared_frame_cache.py
│  └─ wgc_backend.py
├─ workers/
│  ├─ async_tasks.py
│  ├─ cpu_tasks.py
│  ├─ io_tasks.py
│  └─ scanner_process.py
├─ utils/
│  ├─ __init__.py
│  ├─ bounded_latest_queue.py
│  ├─ memory_config_manager.py
│  ├─ memory_debug_manager.py
│  ├─ memory_optimization_manager.py
│  ├─ memory_performance_monitor.py
│  ├─ memory_template_manager.py
│  ├─ performance_profiler.py
│  ├─ win_dpi.py
│  ├─ win_types.py
│  ├─ memory/
│  │  └─ __init__.py
│  └─ windows/
│     └─ __init__.py
├─ tools/
│  ├─ convert_png_to_ico.py
│  ├─ fix_monitor_config.py
│  ├─ fix_scanner_process_hang.py
│  ├─ fix_wgc_hwnd.py
│  ├─ main_performance_optimizer.py
│  ├─ performance_diagnostic.py
│  ├─ performance_guardian.py
│  ├─ performance_monitor.py
│  ├─ smoke_import_test.py
│  ├─ ui_startup_lag_diagnosis.py
│  ├─ verify_wgc.py
│  └─ wgc_diagnostic_tool.py
├─ assets/
│  ├─ images/
│  │  ├─ approve2.png
│  │  ├─ approve3.png
│  │  ├─ approve_pix.png
│  │  ├─ Run*.png …（省略若干示例）
│  │  └─ template_*.png …（省略若干）
│  ├─ icons/
│  │  └─ icons/
│  │     ├─ custom_icon.ico
│  │     └─ custom_icon_test.png
│  └─ styles/
│     ├─ minimal.qss
│     ├─ modern_flat.qss
│     └─ modern_flat_lite.qss
├─ docs/
│  ├─ WGC修复实施检查清单.md
│  ├─ WGC修复快速参考.md
│  ├─ WGC黑屏问题修复与共享通道优化方案.md
│  └─ 窗口捕获卡死问题优化总结.md
└─ tests/
   ├─ test_import.py
   ├─ test_scanner_process.py
   ├─ test_scanner_fallback.py
   ├─ test_shared_frame_cache.py
   ├─ test_complete_shared_channel.py
   ├─ test_memory_optimization.py
   ├─ test_memory_optimization_simple.py
   ├─ test_memory_optimization_cross_platform.py
   ├─ test_multithreading_architecture.py
   ├─ test_gui_basic.py
   ├─ test_gui_responsiveness.py
   ├─ test_ui_refresh_throttle.py
   ├─ test_bounded_latest_queue.py
   ├─ test_utils.py
   ├─ test_dependency_analysis.py
   ├─ test_conflict_analysis.py
   ├─ test_redundancy_analysis.py
   ├─ test_direct_wgc.py
   ├─ test_auto_hwnd_*.py …（多文件）
   ├─ test_system_status.py
   ├─ test_simple.py
   ├─ simple_*.py
   ├─ verify_process_implementation.py
   └─ project_*/dependency_*/conflict_*/redundancy_* …（报告/计划）
```

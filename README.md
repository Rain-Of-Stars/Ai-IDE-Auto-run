# AI-IDE-Auto-Run-节能版本（开发中）
用PySide6做的Windows小工具，解决Trae IDE的“继续”、Windsurf的“Run”、Codex的“Approve”等等，实现AI IDE的自动化运行。

对Rain-Of-Stars/AI-IDE-Auto-Run进行如下改造：
1) 在auto_approve中新建scheduler.py，类AdaptiveScanScheduler：
   - 状态：active/idle、miss_count、last_hit_ts；
   - 接口：on_hit()、on_miss()、on_foreground_change(app)；
   - 计算下一次扫描延时：命中后进入hit_cooldown_ms；未命中指数退避至miss_backoff_ms_max；非白名单窗口使用idle_scan_interval_ms。
2) 在win_clicker.py接入Windows事件：
   - 优先方案A：使用pywin32的SetWinEventHook监听EVENT_SYSTEM_FOREGROUND，获取当前前台窗口HWND与进程名；维护白名单{Code.exe, Windsurf.exe, Trae.exe}；
   - 方案B(可选)：使用pywinauto.UIA backend尝试查找“Approve/Run/Continue”等控件，若找到直接点击，找不到才唤醒图像匹配；
   - 无感点击使用SendMessageTimeout保护，避免窗口挂起卡死。
3) 在scanner_worker.py：
   - 启动时加载模板，统一做：cv2.IMREAD_GRAYSCALE→Canny/或Sobel→按[0.9,1.0,1.1]构建金字塔；缓存到TemplateBank；
   - 每轮扫描从Scheduler获取延时；只处理“当前前台HWND的client rect与配置ROI的交集”，优先使用PrintWindow/BitBlt抓该区域，失败再回退mss整屏；
   - 匹配逻辑改为：先边缘域matchTemplate(TM_CCOEFF_NORMED)；多模板排队，同一时刻最多2个；阈值命中后触发on_hit()并进入冷却；
   - 所有中间数组预分配，循环中复用缓冲；禁止不必要的copy和颜色空间转换。
4) 多屏策略：
   - 通过前台窗口的HWND定位其所在显示器，只在该屏或其覆盖屏扫描；移除默认全屏轮询，保留“强制轮询模式”为兼容选项(enable_multi_screen_polling=false)。
5) 配置(config_manager.py+settings_dialog.py)新增项并给默认值：
   - scan_mode、active_scan_interval_ms=120、idle_scan_interval_ms=2000、miss_backoff_ms_max=5000、hit_cooldown_ms=4000、process_whitelist、bind_roi_to_hwnd；
   - 向下兼容：旧配置缺失时填默认。
6) tools更新：
   - diagnose_multiscreen_click.py输出“前台窗口→所属显示器→实际扫描矩形”的叠图PNG；
   - fix_multiscreen_config.py支持一键把ROI绑定到前台HWND client rect。
# -*- coding: utf-8 -*-
"""
窗口级截屏(WGC) Demo：输入窗口标题→连续抓帧→OpenCV模板匹配→命中率统计。
- 可在窗口被遮挡/最小化时抓帧；
- 失败自动回退到 PrintWindow（由管理器内部处理）；
- 保存首帧与命中结果为PNG到当前目录。
"""
from __future__ import annotations
import os
import time
from typing import List

import cv2
import numpy as np

from auto_approve.config_manager import load_config, save_config
from auto_approve.wgc_capture import WindowCaptureManager, find_window_by_title
from auto_approve.path_utils import get_app_base_dir


def load_first_template(cfg) -> np.ndarray | None:
    """加载第一张模板图像（BGR）。"""
    paths: List[str] = cfg.template_paths if getattr(cfg, 'template_paths', []) else [cfg.template_path]
    for p in paths:
        p = p.strip()
        if not p:
            continue
        if not os.path.isabs(p):
            # 相对路径基于项目根目录
            proj_root = get_app_base_dir()
            p = os.path.join(proj_root, p)
        if os.path.exists(p):
            img = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                return img
    return None


def main():
    cfg = load_config()
    title = (cfg.target_window_title or input("请输入目标窗口标题(可空跳过): ").strip())
    hwnd = int(getattr(cfg, 'target_hwnd', 0) or 0)
    if hwnd <= 0 and title:
        hwnd = find_window_by_title(title, getattr(cfg, 'window_title_partial_match', True)) or 0
    if hwnd <= 0:
        print("未找到窗口，请配置 config.json 的 target_hwnd 或 target_window_title")
        return

    cfg.capture_backend = 'window'
    cfg.target_hwnd = hwnd
    save_config(cfg)

    tpl = load_first_template(cfg)
    if tpl is None:
        print("未找到模板图片，演示仍继续但匹配分数可能无意义")

    mgr = WindowCaptureManager(target_hwnd=hwnd, fps_max=getattr(cfg, 'fps_max', 30),
                               timeout_ms=getattr(cfg, 'capture_timeout_ms', 5000),
                               restore_minimized=getattr(cfg, 'restore_minimized_noactivate', True))

    total = 30
    hits = 0
    first_saved = False

    for i in range(total):
        frame = mgr.capture_frame(restore_after_capture=getattr(cfg, 'restore_minimized_after_capture', False))
        if frame is None:
            print(f"[{i+1}/{total}] 抓帧失败")
            time.sleep(0.2)
            continue

        if not first_saved:
            cv2.imwrite(f"wgc_demo_first_frame_{int(time.time())}.png", frame)
            first_saved = True

        score = 0.0
        if tpl is not None:
            try:
                img = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if getattr(cfg, 'grayscale', True) else frame
                tplg = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY) if getattr(cfg, 'grayscale', True) else tpl
                res = cv2.matchTemplate(img, tplg, cv2.TM_CCOEFF_NORMED)
                _, score, _, loc = cv2.minMaxLoc(res)
                if score >= getattr(cfg, 'threshold', 0.88):
                    hits += 1
                    h, w = tplg.shape[:2]
                    vis = frame.copy()
                    cv2.rectangle(vis, loc, (loc[0]+w, loc[1]+h), (0, 255, 0), 2)
                    cv2.imwrite(f"wgc_demo_hit_{i+1}.png", vis)
            except Exception:
                pass

        print(f"[{i+1}/{total}] score={score:.3f}")
        time.sleep(0.2)

    mgr.cleanup()
    print(f"完成：命中 {hits}/{total}，命中率={(hits/total*100):.1f}%")


if __name__ == '__main__':
    main()


#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os

print("Python version:", sys.version)
print("Current directory:", os.getcwd())
print("Python path:", sys.path[0])

try:
    from auto_approve.config_manager import load_config
    config = load_config()
    print("Config loaded successfully")
    print("Interval:", config.interval_ms)
    print("FPS max:", getattr(config, 'fps_max', 'Not set'))
    print("Template paths:", len(getattr(config, 'template_paths', [])))
except Exception as e:
    print("Error loading config:", e)
    import traceback
    traceback.print_exc()

try:
    from capture.capture_manager import CaptureManager
    print("CaptureManager imported successfully")
except Exception as e:
    print("Error importing CaptureManager:", e)
    import traceback
    traceback.print_exc()

print("Test completed")

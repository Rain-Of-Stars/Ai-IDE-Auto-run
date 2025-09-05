# 依赖检查与优化报告

## 📊 当前依赖分析

### 第三方库依赖
根据代码分析，项目实际使用的第三方库：

1. **PySide6** - Qt6 GUI框架
   - 使用模块：QtWidgets, QtCore, QtGui
   - 状态：✅ 核心依赖，必需

2. **numpy** - 数值计算库
   - 使用场景：图像处理、数组操作
   - 状态：✅ 核心依赖，必需

3. **opencv-python** (cv2) - 计算机视觉库
   - 使用场景：图像处理、模板匹配
   - 状态：✅ 核心依赖，必需

4. **psutil** - 系统监控库
   - 使用场景：性能监控、进程管理
   - 状态：✅ 性能优化必需

5. **windows-capture** - Windows屏幕捕获
   - 使用场景：WGC屏幕捕获
   - 状态：✅ Windows平台必需

6. **Pillow** (PIL) - 图像处理库
   - 使用场景：图像格式转换
   - 状态：⚠️ 可能冗余，与opencv功能重叠

7. **requests** - HTTP请求库
   - 使用场景：网络请求
   - 状态：❓ 需确认实际使用

8. **aiohttp** - 异步HTTP库
   - 使用场景：异步网络请求
   - 状态：❓ 需确认实际使用

9. **websockets** - WebSocket库
   - 使用场景：WebSocket通信
   - 状态：❓ 需确认实际使用

10. **qasync** - Qt异步支持
    - 使用场景：Qt与asyncio集成
    - 状态：❓ 可选依赖

### 标准库使用
项目大量使用Python标准库，包括：
- **os, sys, pathlib** - 文件系统操作
- **threading, multiprocessing** - 并发处理
- **time, datetime** - 时间处理
- **json, pickle** - 数据序列化
- **logging** - 日志记录
- **ctypes** - Windows API调用
- **typing** - 类型注解
- **dataclasses** - 数据类
- **collections, queue** - 数据结构

## 🔍 依赖问题识别

### 1. 冗余依赖
- **Pillow vs OpenCV**: 两者都提供图像处理功能，存在功能重叠
- **requests vs aiohttp**: 同时存在同步和异步HTTP库

### 2. 可能未使用的依赖
需要进一步确认以下包的实际使用：
- **requests**: 在代码中未发现明显使用
- **aiohttp**: 仅在async_tasks模块中可选使用
- **websockets**: 未发现明显使用

### 3. 版本固定问题
requirements.txt中版本过于严格，可能导致兼容性问题：
```
PySide6==6.9.2  # 建议使用范围版本
numpy==1.26.4   # 建议使用范围版本
```

## 🛠️ 优化建议

### 1. 移除冗余依赖
```diff
# 移除Pillow，使用OpenCV替代
- Pillow==11.3.0
```

### 2. 确认网络库使用
- 如果不需要网络功能，移除 requests, aiohttp, websockets
- 如果需要，保留其中一个（建议requests用于简单HTTP请求）

### 3. 版本范围优化
```diff
# 使用版本范围而非固定版本
- PySide6==6.9.2
+ PySide6>=6.7.2,<7.0.0

- numpy==1.26.4
+ numpy>=1.24.0,<2.0.0

- opencv-python==4.8.1.78
+ opencv-python>=4.8.0,<5.0.0
```

### 4. 可选依赖分离
将可选功能的依赖分离：
```ini
# requirements.txt - 核心依赖
PySide6>=6.7.2,<7.0.0
numpy>=1.24.0,<2.0.0
opencv-python>=4.8.0,<5.0.0
psutil>=5.9.0,<6.0.0
windows-capture>=1.0.0,<2.0.0

# requirements-optional.txt - 可选依赖
qasync>=0.28.0,<1.0.0  # Qt异步支持
requests>=2.32.0,<3.0.0  # HTTP请求（如需要）
```

## 📋 优化后的requirements.txt

```ini
# AI_IDE_Auto_Run 项目核心依赖包

# 核心GUI框架
PySide6>=6.7.2,<7.0.0

# 图像处理和计算机视觉
numpy>=1.24.0,<2.0.0
opencv-python>=4.8.0,<5.0.0

# 系统监控和性能
psutil>=5.9.0,<6.0.0

# Windows系统集成
windows-capture>=1.0.0,<2.0.0

# 可选：Qt异步支持（如果使用异步功能）
# qasync>=0.28.0,<1.0.0

# 可选：网络请求（如果需要网络功能）
# requests>=2.32.0,<3.0.0
```

## 🎯 下一步行动

1. **确认网络库使用**: 检查代码中是否真正使用了requests/aiohttp/websockets
2. **测试Pillow移除**: 确认移除Pillow后功能正常
3. **版本兼容性测试**: 使用版本范围测试兼容性
4. **文档更新**: 更新安装文档，说明可选依赖

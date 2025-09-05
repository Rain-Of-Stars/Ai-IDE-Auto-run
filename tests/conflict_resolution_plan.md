# 冲突解决方案

## 📋 冲突分析总结

根据冲突分析报告，项目中存在以下主要冲突：

### 1. 类名冲突 (5个)
- **PerformanceMetrics**: 在3个文件中重复定义
- **PerformanceStats**: 在2个文件中重复定义  
- **POINT**: 在2个文件中重复定义
- **RECT**: 在3个文件中重复定义
- **MockNumpy**: 在2个测试文件中重复定义

### 2. 文件名冲突 (2个)
- **performance_monitor.py**: 在auto_approve和tools目录中重复
- **__init__.py**: 在多个包中存在（正常情况）

### 3. 函数名冲突 (82个)
- **main**: 在28个文件中重复（正常情况）
- **__init__**: 在67个文件中重复（正常情况）
- 其他方法名冲突

## 🛠️ 解决方案

### 1. 统一性能相关类定义

#### 方案1：创建统一的性能数据类模块
创建 `auto_approve/performance_types.py` 统一定义所有性能相关的数据类：

```python
# auto_approve/performance_types.py
from dataclasses import dataclass, field
import time

@dataclass
class PerformanceMetrics:
    """统一的性能指标数据类"""
    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    scan_time_ms: float = 0.0
    match_time_ms: float = 0.0
    template_count: int = 0
    adaptive_interval_ms: int = 0
    fps: float = 0.0
    # 扩展字段
    capture_time_ms: float = 0.0
    total_scan_time_ms: float = 0.0
    frame_size_kb: float = 0.0
    io_operations: int = 0

@dataclass  
class PerformanceStats:
    """统一的性能统计数据类"""
    operation_name: str = ""
    total_calls: int = 0
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    min_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    p99_duration_ms: float = 0.0
    # 扩展字段
    avg_scan_time: float = 0.0
    avg_match_time: float = 0.0
    cpu_usage_estimate: float = 0.0
    memory_usage_mb: float = 0.0
    frames_processed: int = 0
    templates_matched: int = 0
    last_update: float = 0.0
```

#### 方案2：重构现有文件
1. **保留** `auto_approve/performance_monitor.py` 中的定义作为主要版本
2. **重命名** `tools/performance_monitor.py` 为 `tools/performance_diagnostic.py`
3. **更新** 所有导入引用

### 2. 统一Windows API结构体

#### 创建 `utils/win_types.py` 统一定义：

```python
# utils/win_types.py
import ctypes
from ctypes import wintypes

class POINT(ctypes.Structure):
    """Windows POINT 结构体"""
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

class RECT(ctypes.Structure):
    """Windows RECT 结构体"""
    _fields_ = [
        ("left", wintypes.LONG), 
        ("top", wintypes.LONG),
        ("right", wintypes.LONG), 
        ("bottom", wintypes.LONG)
    ]
```

### 3. 文件重命名方案

#### 重命名冲突文件：
- `tools/performance_monitor.py` → `tools/performance_diagnostic_tool.py`

### 4. 测试文件冲突解决

#### 合并MockNumpy类：
创建 `tests/test_utils.py` 统一测试工具：

```python
# tests/test_utils.py
class MockNumpy:
    """统一的NumPy模拟类"""
    # 合并两个文件中的实现
```

## 📝 实施步骤

### 第一阶段：创建统一模块
1. ✅ 创建 `auto_approve/performance_types.py`
2. ✅ 创建 `utils/win_types.py`  
3. ✅ 创建 `tests/test_utils.py`

### 第二阶段：更新导入
1. 🔄 更新所有文件的导入语句
2. 🔄 替换重复的类定义
3. 🔄 测试功能完整性

### 第三阶段：文件重命名
1. 🔄 重命名 `tools/performance_monitor.py`
2. 🔄 更新相关引用
3. 🔄 更新文档

### 第四阶段：清理验证
1. 🔄 删除重复定义
2. 🔄 运行完整测试
3. 🔄 验证功能正常

## 🎯 预期效果

### 解决的问题：
- ✅ 消除类名冲突
- ✅ 统一数据结构定义
- ✅ 减少代码重复
- ✅ 提高维护性

### 保持的功能：
- ✅ 所有现有功能正常工作
- ✅ API接口保持兼容
- ✅ 性能监控功能完整

## ⚠️ 注意事项

1. **向后兼容**: 确保现有代码仍能正常工作
2. **测试覆盖**: 每个修改都要有对应测试
3. **文档更新**: 同步更新相关文档
4. **渐进式修改**: 分阶段实施，避免大规模破坏性变更

## 📊 影响评估

### 修改文件数量：
- 直接修改：约15个文件
- 导入更新：约30个文件
- 测试更新：约10个文件

### 风险等级：**中等**
- 主要是重构和整理，不涉及核心逻辑
- 有完整的测试覆盖
- 可以分步骤实施和验证

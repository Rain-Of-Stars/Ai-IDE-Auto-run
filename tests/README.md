# 测试文件夹

本文件夹包含项目的所有测试文件，用于验证各个功能模块的正确性。

## 文件结构

```
tests/
├── __init__.py                           # 测试包初始化文件
├── README.md                             # 本说明文件
├── run_all_tests.py                      # 测试运行器
├── test_duplicate_check.py               # 重复文件检查功能测试
├── test_final_relative_path.py           # 相对路径功能测试
├── test_add_template_relative_path.py    # 添加模板相对路径测试
├── test_settings_dialog_add_template.py  # 设置对话框添加模板测试
└── demo_duplicate_check.py               # 重复文件检查演示
```

## 测试说明

### 核心测试文件

1. **test_duplicate_check.py**
   - 测试重复文件检查功能
   - 验证添加相同内容的图片时不会重复复制
   - 验证文件哈希计算的正确性

2. **test_final_relative_path.py**
   - 测试完整的相对路径工作流程
   - 验证项目根目录识别
   - 验证assets/images目录处理
   - 验证路径解析功能

3. **test_add_template_relative_path.py**
   - 测试添加模板图片时使用相对路径的功能
   - 验证文件复制到assets/images目录
   - 验证文件名冲突处理

4. **test_settings_dialog_add_template.py**
   - 测试设置对话框添加模板图片功能
   - 模拟完整的添加模板工作流程
   - 验证图片处理和路径管理

### 演示文件

1. **demo_duplicate_check.py**
   - 演示重复文件检查功能的使用
   - 提供交互式的功能展示

## 运行测试

### 运行所有测试

```bash
# 在项目根目录下运行
python tests/run_all_tests.py
```

### 运行单个测试

```bash
# 在项目根目录下运行
python tests/test_duplicate_check.py
python tests/test_final_relative_path.py
python tests/test_add_template_relative_path.py
python tests/test_settings_dialog_add_template.py
```

### 运行演示

```bash
# 在项目根目录下运行
python tests/demo_duplicate_check.py
```

## 测试环境要求

- Python 3.7+
- PIL/Pillow（用于图片处理测试）
- 项目依赖包（见requirements.txt）

## 注意事项

1. **运行目录**: 所有测试都应该在项目根目录下运行，测试文件会自动处理路径问题
2. **临时文件**: 测试会创建临时文件和目录，运行完成后会自动清理
3. **配置文件**: 某些测试可能会临时修改配置，但会在测试结束后恢复
4. **依赖检查**: 如果缺少PIL等依赖，相关测试会跳过图片处理部分

## 添加新测试

当添加新的测试文件时，请遵循以下规范：

1. 文件名以`test_`开头
2. 在文件开头添加项目根目录到Python路径：
   ```python
   import sys
   import os
   sys.path.insert(0, os.path.abspath('..'))
   ```
3. 包含完整的文档字符串说明测试目的
4. 实现适当的清理逻辑
5. 提供清晰的测试结果输出

测试文件会被`run_all_tests.py`自动发现和运行。
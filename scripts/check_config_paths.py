# -*- coding: utf-8 -*-
"""
简单校验：加载配置并检查模板路径是否存在。
仅用于本地快速自检，不影响正式功能。
"""
import json
import os

from auto_approve.config_manager import load_config


def main() -> None:
    # 加载配置
    cfg = load_config()
    # 取多模板列表；为空则回退到单路径
    paths = list(cfg.template_paths) if getattr(cfg, "template_paths", None) else [cfg.template_path]
    # 逐个检查存在性（相对路径会基于当前工作目录解析）
    result = {
        "cwd": os.getcwd(),
        "paths": paths,
        "exists": [os.path.exists(p) for p in paths],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


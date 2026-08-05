#!/usr/bin/env python3
"""ds-vision-skill 独立入口。

用法（在 skill 根目录下）：
  python scripts/run.py <文件路径> [--prompt TEXT] [--intent auto|reason|ocr|document]
                        [--complex] [--accurate-ocr] [--json] [--no-cache]

自动将 skill 内的 ds_vision 包加入 sys.path，无需 pip 安装。
"""

import os
import sys

# 加入 ds_vision 包路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path

from ds_vision.config import load_dotenv
from ds_vision.router import route

# skill 根目录（scripts 的上一级），优先从这里加载 .env
_SKILL_ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    path = argv[0]
    # 解析参数
    prompt = 'Analyze this visual input and return the useful content.'
    intent = "auto"
    complex_ = False
    accurate_ocr = False
    json_mode = False
    no_cache = False

    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--prompt":
            i += 1
            prompt = argv[i]
        elif a == "--intent":
            i += 1
            intent = argv[i]
        elif a == "--complex":
            complex_ = True
        elif a == "--accurate-ocr":
            accurate_ocr = True
        elif a == "--json":
            json_mode = True
        elif a == "--no-cache":
            no_cache = True
        i += 1

    load_dotenv(_SKILL_ROOT / ".env")
    env, code = route(
        path,
        prompt=prompt,
        intent=intent,
        complex_=complex_,
        accurate_ocr=accurate_ocr,
        no_cache=no_cache,
    )
    if json_mode:
        print(env.to_json())
    else:
        print(env.result)
    return code


if __name__ == "__main__":
    sys.exit(main())
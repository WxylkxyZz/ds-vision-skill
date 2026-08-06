#!/usr/bin/env python3
"""ds-vision-skill 独立入口。

用法（在 skill 根目录下）：
  python scripts/run.py <文件路径> [--prompt TEXT] [--intent auto|reason|ocr|document]
                        [--complex] [--accurate-ocr] [--json] [--no-cache] [--status]

自动将 skill 内的 ds_vision 包加入 sys.path，无需 pip 安装。
"""

import argparse
import json
import os
import sys
from pathlib import Path

# 加入 ds_vision 包路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ds_vision.config import load_config, load_dotenv, status_report
from ds_vision.router import route

# skill 根目录（scripts 的上一级），优先从这里加载 .env
_SKILL_ROOT = Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ds-vision",
        description="为纯文本推理模型补充视觉能力",
    )
    parser.add_argument("path", nargs="?", help="输入文件路径 (图片/PDF/文档)")
    parser.add_argument(
        "--prompt",
        default="Analyze this visual input and return the useful content.",
        help="分析提示词",
    )
    parser.add_argument(
        "--intent",
        choices=["auto", "reason", "ocr", "document"],
        default="auto",
        help="任务类型 (默认 auto)",
    )
    parser.add_argument(
        "--complex",
        action="store_true",
        help="复杂视觉推理 (图表/数学/UI)，首选 thinking 模型",
    )
    parser.add_argument(
        "--accurate-ocr",
        action="store_true",
        help="百度高精度 OCR (accurate_basic)",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="输出标准 JSON Envelope",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="强制重新调用 API",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="打印通道状态报告后退出 (不处理文件)",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    load_dotenv(_SKILL_ROOT / ".env")

    if args.status:
        cfg = load_config()
        print(json.dumps(status_report(cfg), ensure_ascii=False, indent=2))
        return 0

    if not args.path:
        parser.error("缺少位置参数: path（或使用 --status 查看通道状态）")

    cfg = load_config()
    env, code = route(
        args.path,
        prompt=args.prompt,
        intent=args.intent,
        complex_=args.complex,
        accurate_ocr=args.accurate_ocr,
        no_cache=args.no_cache,
        cfg=cfg,
    )
    print(env.to_json() if args.json_output else env.result)
    return code


if __name__ == "__main__":
    sys.exit(main())

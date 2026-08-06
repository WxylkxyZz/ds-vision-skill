"""router：统一入口，自动路由 + 通道降级链编排。

按 intent 构建降级链，跨链兜底时合并 attempts 记录。
"""

from __future__ import annotations

import os
from typing import Tuple

from . import envelope
from .cache import Cache
from .channels.base import Chain
from .channels.document import MinerUChannel
from .channels.ocr import BaiduOCRChannel
from .channels.vlm import VLMChannel
from .config import Config
from .envelope import Envelope, EXIT_GENERIC, EXIT_OK
from .utils import guess_intent, is_image


def _build_vlm_chain(
    cfg: Config, complex_: bool = False, prompt: str = ""
) -> Chain:
    """构建 VLM 降级链。

    顺序：primary(由 complex_ 决定) -> secondary(另一 GLM 通道) -> custom(已配置)。
    """
    primary = "glm-thinking" if complex_ else "glm"
    secondary = "glm" if complex_ else "glm-thinking"

    desired = [
        VLMChannel(primary),
        VLMChannel(secondary),
        VLMChannel("custom"),
    ]

    # 按可用性过滤：custom 需配置齐全；glm/glm-thinking 始终保留
    # （缺失 key 会在 attempt 内返回 EXIT_AUTH 触发降级，而非被剔除）
    channels = [
        ch
        for ch in desired
        if ch.channel_name != "custom"
        or (cfg.custom.api_key and cfg.custom.base_url and cfg.custom.model)
    ]
    return Chain(channels, task_type="image_reasoning")


def vlm_chain(
    image_path: str,
    prompt: str,
    cfg: Config,
    cache: Cache,
    complex_: bool = False,
    no_cache: bool = False,
) -> Tuple[Envelope, int]:
    """VLM 降级链：glm -> glm-thinking -> custom。"""
    chain = _build_vlm_chain(cfg, complex_, prompt)
    return chain.run(image_path, prompt=prompt, cfg=cfg, cache=cache, no_cache=no_cache)


def route(
    path: str,
    prompt: str = "Analyze this visual input and return the useful content.",
    intent: str = "auto",
    complex_: bool = False,
    accurate_ocr: bool = False,
    no_cache: bool = False,
    cfg: Config = None,
    cache: Cache = None,
) -> Tuple[Envelope, int]:
    """统一路由入口。返回 (envelope, exit_code)。"""
    if not os.path.exists(path):
        return (
            envelope.fail("unknown", result=f"Input not found: {path}", code=1),
            1,
        )

    if cfg is None:
        from .config import load_config

        cfg = load_config()
    if cache is None:
        cache = Cache(cfg.cache_dir)

    # 解析 intent
    if intent == "auto":
        from pathlib import Path as _P

        intent = guess_intent(_P(path).suffix, prompt)

    attempts = []

    if intent == "document":
        chain = Chain(
            [MinerUChannel("vlm"), MinerUChannel("pipeline")],
            task_type="document_parsing",
        )
        env, code = chain.run(path, prompt="", cfg=cfg, cache=cache, no_cache=no_cache)
        if code == EXIT_OK and env.result:
            return env, code
        attempts.extend(env.metadata.get("attempts", []))
        # 文档解析失败，若目标是图片则退回 OCR / 视觉
        if is_image(path):
            ocr_chain = Chain(
                [BaiduOCRChannel(accurate_ocr)], task_type="ocr"
            )
            env, code = ocr_chain.run(path, prompt="", cfg=cfg, cache=cache, no_cache=no_cache)
            attempts.extend(env.metadata.get("attempts", []))
            if code == EXIT_OK and env.result.strip():
                env.metadata["attempts"] = attempts
                return env, code
            env2, code2 = vlm_chain(path, prompt, cfg, cache, complex_, no_cache)
            env2.metadata["attempts"] = attempts + env2.metadata.get("attempts", [])
            return env2, code2
        return env, code

    if intent == "ocr":
        ocr_chain = Chain([BaiduOCRChannel(accurate_ocr)], task_type="ocr")
        env, code = ocr_chain.run(path, prompt="", cfg=cfg, cache=cache, no_cache=no_cache)
        if code == EXIT_OK and env.result.strip():
            return env, code
        attempts.extend(env.metadata.get("attempts", []))
        # OCR 失败退回视觉理解（无 Tesseract）
        env2, code2 = vlm_chain(path, prompt, cfg, cache, complex_, no_cache)
        env2.metadata["attempts"] = attempts + env2.metadata.get("attempts", [])
        return env2, code2

    # intent == reason / 默认
    return vlm_chain(path, prompt, cfg, cache, complex_, no_cache)

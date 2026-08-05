"""router：统一入口，自动路由 + 通道降级。

对应原项目 scripts/vision-router.ps1。
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

from . import envelope
from .channels import document as doc_mod
from .channels import ocr as ocr_mod
from .channels import vlm as vlm_mod
from .config import load_config
from .utils import guess_intent, is_image, port_open


def vlm_chain(
    image_path: str,
    prompt: str,
    complex_: bool = False,
    no_cache: bool = False,
) -> Tuple[envelope.Envelope, int]:
    """VLM 降级链：glm -> glm-thinking -> custom -> local。

    通道顺序：优先按 complex_ 决定首通道，其余按配置可用性补齐。
    """
    cfg = load_config()
    order = []
    primary = "glm-thinking" if complex_ else "glm"
    if primary == "glm":
        order.append("glm")
        order.append("glm-thinking")
    else:
        order.append("glm-thinking")
        order.append("glm")

    if cfg["custom"].api_key and cfg["custom"].base_url and cfg["custom"].model:
        if "custom" not in order:
            order.append("custom")

    # 探测本地运行时
    local_available = any(
        port_open(host, port)
        for host, port in [
            ("127.0.0.1", 11434),
            ("127.0.0.1", 1234),
            ("127.0.0.1", 8080),
        ]
    )
    if local_available and "local" not in order:
        order.append("local")

    attempts = []
    for ch in order:
        env, code = vlm_mod.vlm_reason(
            image_path,
            prompt=prompt,
            channel=ch,
            json_mode=True,
            no_cache=no_cache,
        )
        attempts.append({"name": ch, "code": code})
        if code == vlm_mod.EXIT_OK and env.result.strip():
            env.metadata["attempts"] = attempts
            return env, code

    last = attempts[-1]["name"] if attempts else "none"
    return envelope.fail(
        "image_reasoning",
        result=f"视觉通道全部失败 (最后: {last})",
        attempts=attempts,
    ), vlm_mod.EXIT_GENERIC


def route(
    path: str,
    prompt: str = "Analyze this visual input and return the useful content.",
    intent: str = "auto",
    complex_: bool = False,
    accurate_ocr: bool = False,
    no_cache: bool = False,
) -> Tuple[envelope.Envelope, int]:
    """统一路由入口。返回 (envelope, exit_code)。"""
    if not os.path.exists(path):
        return envelope.fail("unknown", result=f"Input not found: {path}"), 1

    # 解析 intent
    if intent == "auto":
        from pathlib import Path as _P

        intent = guess_intent(_P(path).suffix, prompt)

    attempts = []

    if intent == "document":
        env, code = doc_mod.document_chain(path)
        if code == doc_mod.EXIT_OK and env.result:
            return env, code
        attempts.extend(env.metadata.get("attempts", []))
        # 文档解析失败，若目标是图片则退回 OCR / 视觉
        if is_image(path):
            env, code = ocr_mod.ocr_chain(path, accurate_ocr)
            attempts.extend(env.metadata.get("attempts", []))
            if code == ocr_mod.EXIT_OK and env.result.strip():
                env.metadata["attempts"] = attempts
                return env, code
            env2, code2 = vlm_chain(path, prompt, complex_, no_cache)
            env2.metadata["attempts"] = attempts + env2.metadata.get("attempts", [])
            return env2, code2
        return env, code

    if intent == "ocr":
        env, code = ocr_mod.ocr_chain(path, accurate_ocr)
        if code == ocr_mod.EXIT_OK and env.result.strip():
            return env, code
        attempts.extend(env.metadata.get("attempts", []))
        # OCR 失败退回视觉理解
        env2, code2 = vlm_chain(path, prompt, complex_, no_cache)
        env2.metadata["attempts"] = attempts + env2.metadata.get("attempts", [])
        return env2, code2

    # intent == reason / 默认
    return vlm_chain(path, prompt, complex_, no_cache)
"""VLM 视觉理解通道。

支持通道：glm / glm-thinking / custom / local。
统一走 OpenAI 兼容 chat/completions 接口，图片以 base64 data URL 传入。
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import requests

from .. import envelope
from ..cache import Cache, vlm_cache_key, sha256_file
from ..config import load_config
from ..utils import file_size_mb, encode_image_base64, port_open

LOCAL_PROBES = [
    ("ollama", "http://127.0.0.1:11434/v1/chat/completions"),
    ("lmstudio", "http://127.0.0.1:1234/v1/chat/completions"),
    ("llamacpp", "http://127.0.0.1:8080/v1/chat/completions"),
]

# 退出码约定（与原项目一致）
EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_AUTH = 2
EXIT_RATE_LIMIT = 3
EXIT_NETWORK = 4
EXIT_REJECTED = 5


class VLMError(Exception):
    def __init__(self, message: str, code: int = EXIT_GENERIC):
        super().__init__(message)
        self.code = code


def _resolve_config(channel: str) -> Tuple[str, str, str]:
    """返回 (base_url, api_key, model)。"""
    cfg = load_config()
    if channel in ("glm", "glm-thinking"):
        g = cfg["glm"]
        model = g.thinking_model if channel == "glm-thinking" else g.fast_model
        return g.base_url, g.api_key, model
    if channel == "custom":
        c = cfg["custom"]
        if not (c.base_url and c.api_key and c.model):
            raise VLMError("custom channel 未配置 VISION_CUSTOM_*", EXIT_AUTH)
        return c.base_url, c.api_key, c.model
    if channel == "local":
        return _resolve_local(cfg)
    raise VLMError(f"未知通道: {channel}", EXIT_GENERIC)


def _resolve_local(cfg: Dict[str, Any]) -> Tuple[str, str, str]:
    """探测本地运行时，返回 (url, key, model)。"""
    for name, url in LOCAL_PROBES:
        host, port = url.split("//")[1].split(":")[0], int(
            url.rsplit(":", 1)[1].split("/")[0]
        )
        if port_open(host, port):
            model = cfg.get("local_model") or {
                "ollama": "qwen2.5-vl:3b",
                "lmstudio": "",
                "llamacpp": "",
            }.get(name)
            if not model:
                raise VLMError(
                    f"本地通道 {name} 需要设置 VISION_LOCAL_MODEL 指定模型", EXIT_AUTH
                )
            return url, "", model
    raise VLMError(
        "未找到本地视觉运行时 (ollama 11434 / lmstudio 1234 / llamacpp 8080)",
        EXIT_GENERIC,
    )


def normalize_chat_url(url: str) -> str:
    url = url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    return url


def vlm_reason(
    image_path: str,
    prompt: str = "Describe this image in detail.",
    channel: str = "glm",
    json_mode: bool = True,
    no_cache: bool = False,
    timeout: int = 90,
) -> Tuple[Optional[envelope.Envelope], int]:
    """执行一次 VLM 视觉推理。返回 (envelope, exit_code)。"""
    import os

    if not os.path.exists(image_path):
        return envelope.fail("image_reasoning", result=f"image not found: {image_path}"), EXIT_GENERIC

    if file_size_mb(image_path) > 15:
        return (
            envelope.fail(
                "image_reasoning", result="图片过大(>15MB)，请先降采样或用文档通道。"
            ),
            EXIT_GENERIC,
        )

    try:
        base_url, api_key, model = _resolve_config(channel)
    except VLMError as e:
        return envelope.fail("image_reasoning", result=str(e)), e.code

    base_url = normalize_chat_url(base_url)

    # 缓存查询
    cache = Cache(load_config()["cache_dir"])
    img_sha = sha256_file(image_path)
    key = vlm_cache_key(cache, img_sha, prompt, channel, model)
    if not no_cache:
        cached = cache.get(key)
        if cached and cached.get("result"):
            env = envelope.ok(
                cached.get("task_type", "image_reasoning"),
                cached.get("tool_used", channel),
                cached["result"],
                cached.get("confidence", "high"),
                {**cached.get("metadata", {}), "cached": True},
            )
            return env, EXIT_OK

    if not api_key and channel != "local":
        return envelope.fail("image_reasoning", result=f"缺少 {channel} 的 API Key"), EXIT_AUTH

    # 构造请求
    content: list = [{"type": "image_url", "image_url": {"url": encode_image_base64(image_path)}}]
    if prompt:
        content.append({"type": "text", "text": prompt})
    body = {"model": model, "messages": [{"role": "user", "content": content}]}

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    import time

    t0 = time.time()
    try:
        resp = requests.post(base_url, json=body, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        return envelope.fail("image_reasoning", result=f"网络错误: {e}"), EXIT_NETWORK

    elapsed_ms = int((time.time() - t0) * 1000)

    if resp.status_code in (401, 403):
        return envelope.fail("image_reasoning", result=f"{channel} 认证失败"), EXIT_AUTH
    if resp.status_code == 429:
        return envelope.fail("image_reasoning", result=f"{channel} 限流"), EXIT_RATE_LIMIT
    if resp.status_code >= 500:
        return envelope.fail("image_reasoning", result=f"{channel} 服务端错误"), EXIT_NETWORK
    if resp.status_code != 200:
        return envelope.fail(
            "image_reasoning", result=f"{channel} 请求被拒 status={resp.status_code}"
        ), EXIT_REJECTED

    try:
        data = resp.json()
        content_out = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        return envelope.fail("image_reasoning", result=f"响应解析失败: {e}"), EXIT_GENERIC

    env = envelope.ok(
        "image_reasoning",
        tool=f"{channel}:{model}",
        result=content_out,
        confidence="high",
        metadata={
            "channel": channel,
            "model": model,
            "image_sha": img_sha[:12],
            "latency_ms": elapsed_ms,
            "cached": False,
        },
    )
    cache.put(key, env.to_dict())
    return env, EXIT_OK
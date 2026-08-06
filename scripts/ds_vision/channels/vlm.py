"""VLM 视觉理解通道。

通道：glm / glm-thinking / custom，统一走 OpenAI 兼容 chat/completions 接口，
图片以 base64 data URL 传入。
"""

from __future__ import annotations

from typing import Any, Tuple

import requests

from .. import envelope
from ..cache import Cache, sha256_file, vlm_cache_key
from ..config import Config
from ..envelope import (
    Envelope,
    EXIT_AUTH,
    EXIT_GENERIC,
    EXIT_NETWORK,
    EXIT_OK,
    EXIT_RATE_LIMIT,
    EXIT_REJECTED,
)
from ..utils import encode_image_base64, file_size_mb
from .base import BaseChannel


class VLMError(Exception):
    def __init__(self, message: str, code: int = EXIT_GENERIC):
        super().__init__(message)
        self.code = code


def normalize_chat_url(url: str) -> str:
    url = url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    return url


class VLMChannel(BaseChannel):
    """统一 VLM 通道。channel_name 决定模型与端点来源。

    Args:
        channel_name: glm | glm-thinking | custom
    """

    task_type = "image_reasoning"

    def __init__(self, channel_name: str):
        if channel_name not in ("glm", "glm-thinking", "custom"):
            raise VLMError(f"未知通道: {channel_name}", EXIT_GENERIC)
        self.channel_name = channel_name
        self.name = channel_name

    # -- 配置解析 -----------------------------------------------------------

    def _resolve(self, cfg: Config) -> Tuple[str, str, str]:
        """返回 (base_url, api_key, model)。"""
        if self.channel_name in ("glm", "glm-thinking"):
            g = cfg.glm
            model = g.thinking_model if self.channel_name == "glm-thinking" else g.fast_model
            return g.base_url, g.api_key, model
        # custom
        c = cfg.custom
        if not (c.base_url and c.api_key and c.model):
            raise VLMError("custom 通道未配置 VISION_CUSTOM_*", EXIT_AUTH)
        return c.base_url, c.api_key, c.model

    # -- 主流程 -------------------------------------------------------------

    def attempt(
        self,
        path: str,
        *,
        prompt: str = "Describe this image in detail.",
        cfg: Config,
        cache: Cache,
        no_cache: bool = False,
        timeout: int = 90,
        **kwargs: Any,
    ) -> Tuple[Envelope, int]:
        import os
        import time

        if not os.path.exists(path):
            return envelope.fail(
                "image_reasoning",
                result=f"image not found: {path}",
                code=EXIT_GENERIC,
            ), EXIT_GENERIC

        if file_size_mb(path) > 15:
            return (
                envelope.fail(
                    "image_reasoning",
                    result="图片过大(>15MB)，请先降采样或用文档通道。",
                    code=EXIT_GENERIC,
                ),
                EXIT_GENERIC,
            )

        try:
            base_url, api_key, model = self._resolve(cfg)
        except VLMError as e:
            return envelope.fail("image_reasoning", result=str(e), code=e.code), e.code

        base_url = normalize_chat_url(base_url)

        # 缓存查询
        img_sha = sha256_file(path)
        key = vlm_cache_key(img_sha, prompt, self.channel_name, model)
        if not no_cache:
            cached = cache.get(key)
            if cached and cached.get("result"):
                env = envelope.ok(
                    cached.get("task_type", "image_reasoning"),
                    cached.get("tool_used", self.channel_name),
                    cached["result"],
                    cached.get("confidence", "high"),
                    {**cached.get("metadata", {}), "cached": True},
                )
                return env, EXIT_OK

        if not api_key:
            return (
                envelope.fail(
                    "image_reasoning",
                    result=f"缺少 {self.channel_name} 的 API Key",
                    code=EXIT_AUTH,
                ),
                EXIT_AUTH,
            )

        # 构造请求
        content: list = [
            {"type": "image_url", "image_url": {"url": encode_image_base64(path)}}
        ]
        if prompt:
            content.append({"type": "text", "text": prompt})
        body = {"model": model, "messages": [{"role": "user", "content": content}]}

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        t0 = time.time()
        try:
            resp = requests.post(base_url, json=body, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            return (
                envelope.fail("image_reasoning", result=f"网络错误: {e}", code=EXIT_NETWORK),
                EXIT_NETWORK,
            )

        elapsed_ms = int((time.time() - t0) * 1000)

        if resp.status_code in (401, 403):
            return (
                envelope.fail(
                    "image_reasoning", result=f"{self.channel_name} 认证失败", code=EXIT_AUTH
                ),
                EXIT_AUTH,
            )
        if resp.status_code == 429:
            return (
                envelope.fail(
                    "image_reasoning", result=f"{self.channel_name} 限流", code=EXIT_RATE_LIMIT
                ),
                EXIT_RATE_LIMIT,
            )
        if resp.status_code >= 500:
            return (
                envelope.fail(
                    "image_reasoning", result=f"{self.channel_name} 服务端错误", code=EXIT_NETWORK
                ),
                EXIT_NETWORK,
            )
        if resp.status_code != 200:
            return (
                envelope.fail(
                    "image_reasoning",
                    result=f"{self.channel_name} 请求被拒 status={resp.status_code}",
                    code=EXIT_REJECTED,
                ),
                EXIT_REJECTED,
            )

        try:
            data = resp.json()
            content_out = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            return (
                envelope.fail("image_reasoning", result=f"响应解析失败: {e}", code=EXIT_GENERIC),
                EXIT_GENERIC,
            )

        env = envelope.ok(
            "image_reasoning",
            tool=f"{self.channel_name}:{model}",
            result=content_out,
            confidence="high",
            metadata={
                "channel": self.channel_name,
                "model": model,
                "image_sha": img_sha[:12],
                "latency_ms": elapsed_ms,
                "cached": False,
            },
        )
        cache.put(key, env.to_dict())
        return env, EXIT_OK

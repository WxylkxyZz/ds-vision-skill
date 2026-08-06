"""OCR 通道：百度 OCR（云端）。

OCR 意图失败时由 router 退回 GLM 视觉推理兜底。
百度 access token 自动缓存到 ~/.ds-vision-py/baidu_token.json。
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any, Tuple

import requests

from .. import envelope
from ..cache import Cache
from ..config import Config
from ..envelope import (
    Envelope,
    EXIT_AUTH,
    EXIT_GENERIC,
    EXIT_NETWORK,
    EXIT_OK,
    EXIT_RATE_LIMIT,
)
from .base import BaseChannel

# 百度 OCR 端点
BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
BAIDU_OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/{api}"


def _get_baidu_token(api_key: str, secret_key: str, cache_file: str) -> str:
    """获取百度 access token，带缓存。"""
    token_cache = Path(cache_file)
    if token_cache.exists():
        try:
            data = json.loads(token_cache.read_text(encoding="utf-8"))
            if data.get("expire_at", 0) > time.time() + 60:
                return data["access_token"]
        except Exception:
            pass

    resp = requests.get(
        BAIDU_TOKEN_URL,
        params={
            "grant_type": "client_credentials",
            "client_id": api_key,
            "client_secret": secret_key,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"百度 token 获取失败: {resp.status_code}")
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(
            f"百度 token 响应异常: {data.get('error_description', data)}"
        )
    token_cache.parent.mkdir(parents=True, exist_ok=True)
    token_cache.write_text(
        json.dumps(
            {
                "access_token": data["access_token"],
                "expire_at": time.time() + data.get("expires_in", 2592000),
            }
        ),
        encoding="utf-8",
    )
    return data["access_token"]


class BaiduOCRChannel(BaseChannel):
    """百度 OCR 通道。accurate=True 使用高精度接口。"""

    name = "baidu-ocr"
    task_type = "ocr"

    def __init__(self, accurate: bool = False):
        self.accurate = accurate

    def attempt(
        self,
        path: str,
        *,
        prompt: str = "",
        cfg: Config,
        cache: Cache,
        no_cache: bool = False,
        **kwargs: Any,
    ) -> Tuple[Envelope, int]:
        oc = cfg.baidu_ocr
        if not (oc.api_key and oc.secret_key):
            return (
                envelope.fail(
                    "ocr",
                    result="未配置 BAIDU_API_KEY / BAIDU_SECRET_KEY",
                    code=EXIT_AUTH,
                ),
                EXIT_AUTH,
            )

        t0 = time.time()
        try:
            token = _get_baidu_token(oc.api_key, oc.secret_key, oc.token_cache_file)
        except Exception as e:
            return (
                envelope.fail("ocr", result=f"百度 token 失败: {e}", code=EXIT_AUTH),
                EXIT_AUTH,
            )

        api = "accurate_basic" if self.accurate else "general_basic"
        try:
            img_b64 = base64.b64encode(Path(path).read_bytes()).decode("ascii")
        except OSError as e:
            return (
                envelope.fail("ocr", result=f"读取图片失败: {e}", code=EXIT_GENERIC),
                EXIT_GENERIC,
            )

        try:
            resp = requests.post(
                BAIDU_OCR_URL.format(api=api),
                params={"access_token": token},
                data={"image": img_b64, "language_type": "CHN_ENG"},
                timeout=60,
            )
        except requests.RequestException as e:
            return (
                envelope.fail("ocr", result=f"百度 OCR 网络错误: {e}", code=EXIT_NETWORK),
                EXIT_NETWORK,
            )

        if resp.status_code in (401, 403):
            return (
                envelope.fail("ocr", result="百度 OCR 认证失败", code=EXIT_AUTH),
                EXIT_AUTH,
            )
        if resp.status_code == 429:
            return (
                envelope.fail("ocr", result="百度 OCR 限流", code=EXIT_RATE_LIMIT),
                EXIT_RATE_LIMIT,
            )

        try:
            data = resp.json()
        except ValueError:
            return (
                envelope.fail("ocr", result="百度 OCR 响应解析失败", code=EXIT_GENERIC),
                EXIT_GENERIC,
            )

        if "error_code" in data:
            return (
                envelope.fail(
                    "ocr",
                    result=f"百度 OCR 错误: {data.get('error_msg')}",
                    code=EXIT_GENERIC,
                ),
                EXIT_GENERIC,
            )

        words = [w.get("words", "") for w in data.get("words_result", []) if w.get("words")]
        text = "\n".join(words)
        env = envelope.ok(
            "ocr",
            tool="baidu-ocr",
            result=text,
            confidence="high" if text else "low",
            metadata={
                "api": api,
                "latency_ms": int((time.time() - t0) * 1000),
            },
        )
        return env, EXIT_OK

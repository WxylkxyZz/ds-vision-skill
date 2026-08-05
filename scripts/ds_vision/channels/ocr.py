"""OCR 通道：百度 OCR（云端） + Tesseract（本地离线兜底）。

降级链：baidu-ocr -> tesseract-ocr。
百度 access token 自动缓存到 ~/.ds-vision-py/baidu_token.json。
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Optional, Tuple

import requests

from .. import envelope
from ..config import load_config

EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_AUTH = 2
EXIT_RATE_LIMIT = 3
EXIT_NETWORK = 4

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
        raise RuntimeError(f"百度 token 响应异常: {data.get('error_description', data)}")
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


def baidu_ocr(image_path: str, accurate: bool = False) -> Tuple[Optional[envelope.Envelope], int]:
    cfg = load_config()["baidu_ocr"]
    if not (cfg.api_key and cfg.secret_key):
        return envelope.fail("ocr", result="未配置 BAIDU_API_KEY / BAIDU_SECRET_KEY"), EXIT_AUTH

    t0 = time.time()
    try:
        token = _get_baidu_token(cfg.api_key, cfg.secret_key, cfg.token_cache_file)
    except Exception as e:
        return envelope.fail("ocr", result=f"百度 token 失败: {e}"), EXIT_AUTH

    api = "accurate_basic" if accurate else "general_basic"
    img_b64 = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")

    try:
        resp = requests.post(
            BAIDU_OCR_URL.format(api=api),
            params={"access_token": token},
            data={"image": img_b64, "language_type": "CHN_ENG"},
            timeout=60,
        )
    except requests.RequestException as e:
        return envelope.fail("ocr", result=f"百度 OCR 网络错误: {e}"), EXIT_NETWORK

    if resp.status_code in (401, 403):
        return envelope.fail("ocr", result="百度 OCR 认证失败"), EXIT_AUTH
    if resp.status_code == 429:
        return envelope.fail("ocr", result="百度 OCR 限流"), EXIT_RATE_LIMIT

    try:
        data = resp.json()
    except ValueError:
        return envelope.fail("ocr", result="百度 OCR 响应解析失败"), EXIT_GENERIC

    if "error_code" in data:
        return envelope.fail("ocr", result=f"百度 OCR 错误: {data.get('error_msg')}"), EXIT_GENERIC

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


def tesseract_ocr(image_path: str) -> Tuple[Optional[envelope.Envelope], int]:
    """本地离线 OCR，依赖系统安装的 tesseract。"""
    try:
        from pytesseract import image_to_string
        from PIL import Image
    except ImportError:
        return envelope.fail(
            "ocr",
            result="本地 OCR 需要安装 pytesseract + Pillow，且系统中需有 tesseract。",
        ), EXIT_GENERIC

    t0 = time.time()
    try:
        text = image_to_string(Image.open(image_path), lang="chi_sim+eng")
    except Exception as e:
        return envelope.fail("ocr", result=f"Tesseract OCR 失败: {e}"), EXIT_GENERIC

    env = envelope.ok(
        "ocr",
        tool="tesseract-ocr",
        result=text.strip(),
        confidence="medium",
        metadata={"latency_ms": int((time.time() - t0) * 1000)},
    )
    return env, EXIT_OK


def ocr_chain(image_path: str, accurate: bool = False) -> Tuple[envelope.Envelope, int]:
    """OCR 降级链：baidu -> tesseract。"""
    attempts = []
    env, code = baidu_ocr(image_path, accurate)
    attempts.append({"name": "baidu-ocr", "code": code})
    if code == EXIT_OK and env.result.strip():
        env.metadata["attempts"] = attempts
        return env, EXIT_OK

    env2, code2 = tesseract_ocr(image_path)
    attempts.append({"name": "tesseract-ocr", "code": code2})
    if code2 == EXIT_OK and env2.result.strip():
        env2.metadata["attempts"] = attempts
        return env2, EXIT_OK

    # 全部失败：用视觉通道兜底由 router 处理，这里返回失败信息
    result = env.result or env2.result or "OCR 全部通道失败"
    return envelope.fail("ocr", result=result, attempts=attempts), EXIT_GENERIC
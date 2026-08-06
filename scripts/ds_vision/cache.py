"""缓存模块：按请求指纹复用结果，降低重复调用成本。

- VLM：按 (内容hash + prompt + 通道 + 模型) 组合指纹
- 文档：按 (内容hash + mode) 指纹（已接入 MinerUChannel）
- 百度 OCR：access token 缓存在 ocr 模块单独处理
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _digest(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
    return h.hexdigest()


class Cache:
    """基于 JSON 文件的简单缓存。"""

    def __init__(self, cache_dir: str):
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def put(self, key: str, value: Dict[str, Any]) -> None:
        try:
            self._path(key).write_text(
                json.dumps(value, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass


def vlm_cache_key(img_sha: str, prompt: str, channel: str, model: str) -> str:
    return _digest(img_sha, prompt, channel, model)


def document_cache_key(file_sha: str, mode: str) -> str:
    return _digest("doc", file_sha, mode)

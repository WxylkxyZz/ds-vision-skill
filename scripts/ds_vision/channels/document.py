"""文档解析通道：MinerU 云端解析。

降级链：mineru-vlm(推荐) -> mineru-pipeline(默认管线回退)。``mode`` 真正驱动
``model_version``，使两次降级调用发送不同管线参数（修复原假降级）。
``.html`` / ``.htm`` 文件强制走 ``MinerU-HTML`` 管线（官方文档要求）。

model_version 三个合法取值（经 https://mineru.net/apiManage/docs 核实）：
  pipeline(默认) / vlm(推荐,多模态,含公式表格) / MinerU-HTML(HTML 文件专用)。

MinerU API 流程（v4）：
  1. POST /api/v4/file-urls/batch 申请预签名上传地址（-> batch_id + file_urls）
  2. PUT 上传文件（系统自动触发解析任务）
  3. GET /api/v4/extract-results/batch/{batch_id} 轮询结果（-> full_zip_url）
  4. 下载 zip，提取 markdown

本地文本快捷路径：``.md`` / ``.txt`` 直接读取，不触云。
"""

from __future__ import annotations

import io
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Optional, Tuple

import requests

from .. import envelope
from ..cache import Cache, document_cache_key, sha256_file
from ..config import Config
from ..envelope import (
    Envelope,
    EXIT_AUTH,
    EXIT_GENERIC,
    EXIT_NETWORK,
    EXIT_OK,
)
from ..utils import is_local_text
from .base import BaseChannel

MINERU_BATCH_URL = "https://mineru.net/api/v4/file-urls/batch"
MINERU_RESULTS_URL = "https://mineru.net/api/v4/extract-results/batch/{batch_id}"

# mode -> model_version 映射（经 https://mineru.net/apiManage/docs 官方文档核实）。
# MinerU v4 model_version 三个合法取值：pipeline(默认) / vlm(推荐,多模态,含公式表格) / MinerU-HTML。
# 文档原文：非 HTML 文件可选 pipeline 或 vlm；HTML 文件须明确指定 MinerU-HTML。
# 故降级链按管线能力设计：vlm(推荐) -> pipeline(默认管线回退)；
# .html/.htm 文件在 attempt() 内强制 MinerU-HTML（见 _resolve_model_version）。
MODE_TO_MODEL_VERSION = {
    "vlm": "vlm",
    "pipeline": "pipeline",
}
DEFAULT_MODEL_VERSION = "vlm"


class MinerUError(Exception):
    def __init__(self, message: str, code: int = EXIT_GENERIC):
        super().__init__(message)
        self.code = code


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _apply_upload_urls(token: str, name: str, model_version: str) -> Tuple[str, str]:
    """申请上传地址，返回 (batch_id, upload_url)。"""
    data = {
        "files": [{"name": name, "data_id": str(uuid.uuid4())}],
        "model_version": model_version,
    }
    resp = requests.post(MINERU_BATCH_URL, headers=_headers(token), json=data, timeout=30)
    if resp.status_code in (401, 403):
        raise MinerUError("MinerU 认证失败", EXIT_AUTH)
    if resp.status_code != 200:
        raise MinerUError(f"MinerU 申请上传失败 status={resp.status_code}", EXIT_GENERIC)
    result = resp.json()
    if result.get("code") != 0:
        raise MinerUError(
            f"MinerU 申请上传失败: {result.get('msg') or result.get('message')}",
            EXIT_GENERIC,
        )
    batch_id = result["data"]["batch_id"]
    upload_url = result["data"]["file_urls"][0]
    return batch_id, upload_url


def _download_markdown(zip_url: str) -> str:
    """从结果 zip 包中提取 markdown 文本。"""
    resp = requests.get(zip_url, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        md_files = [n for n in zf.namelist() if n.endswith(".md")]
        if not md_files:
            raise MinerUError("MinerU 结果 zip 中无 markdown 文件", EXIT_GENERIC)
        return zf.read(md_files[0]).decode("utf-8", errors="ignore")


def _poll_result(token: str, batch_id: str, timeout: int = 180) -> str:
    """轮询批量解析结果，返回 markdown 内容。

    MinerU v4 结构：
      data.extract_result[].state = running|done|failed
      data.extract_result[].full_zip_url = 结果 zip 包（含 .md）
    """
    url = MINERU_RESULTS_URL.format(batch_id=batch_id)
    deadline = time.time() + timeout

    while time.time() < deadline:
        resp = requests.get(url, headers=_headers(token), timeout=30)
        if resp.status_code != 200:
            raise MinerUError(f"MinerU 查询结果失败 status={resp.status_code}", EXIT_GENERIC)
        result = resp.json()
        if result.get("code") != 0:
            raise MinerUError(f"MinerU 查询结果异常: {result.get('msg')}", EXIT_GENERIC)

        items = (result.get("data") or {}).get("extract_result") or []
        if not items:
            time.sleep(3)
            continue

        all_done = True
        for item in items:
            state = item.get("state", "")
            if state == "failed":
                raise MinerUError(
                    f"MinerU 解析失败: {item.get('err_msg') or item.get('error')}",
                    EXIT_GENERIC,
                )
            if state == "done":
                zip_url = item.get("full_zip_url")
                if zip_url:
                    return _download_markdown(zip_url)
            else:
                all_done = False
        if all_done:
            raise MinerUError("MinerU 解析完成但未返回 zip 地址", EXIT_GENERIC)
        time.sleep(3)

    raise MinerUError("MinerU 解析超时", EXIT_GENERIC)


class MinerUChannel(BaseChannel):
    """MinerU 文档解析通道。mode(vlm|pipeline) 决定 model_version；.html 强制 MinerU-HTML。"""

    task_type = "document_parsing"

    def __init__(self, mode: str = "vlm"):
        if mode not in MODE_TO_MODEL_VERSION:
            raise ValueError(f"未知 MinerU mode: {mode}（合法值: {list(MODE_TO_MODEL_VERSION)}）")
        self.mode = mode
        self.name = f"mineru-{mode}"

    def _resolve_model_version(self, path: str) -> str:
        """按 mode 解析 model_version；.html/.htm 强制 MinerU-HTML（官方文档要求）。"""
        if Path(path).suffix.lower() in (".html", ".htm"):
            return "MinerU-HTML"
        return MODE_TO_MODEL_VERSION.get(self.mode, DEFAULT_MODEL_VERSION)

    def _local_text(self, path: str) -> Tuple[Envelope, int]:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
        env = envelope.ok(
            "document_parsing",
            tool="local-text",
            result=text,
            confidence="high",
            metadata={"mode": "local-text", "latency_ms": 0},
        )
        return env, EXIT_OK

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
        p = Path(path)
        if not p.exists():
            return (
                envelope.fail(
                    "document_parsing", result=f"文件不存在: {path}", code=EXIT_GENERIC
                ),
                EXIT_GENERIC,
            )

        # 纯文本/简单 Markdown 直接读取，无需云端，也不需要 token
        if is_local_text(path):
            return self._local_text(path)

        token = cfg.mineru_token
        if not token:
            return (
                envelope.fail(
                    "document_parsing",
                    result="未配置 MINERU_TOKEN，文档解析不可用。",
                    code=EXIT_AUTH,
                ),
                EXIT_AUTH,
            )

        model_version = self._resolve_model_version(path)

        # 缓存查询（按内容 + mode）
        file_sha = sha256_file(path)
        key = document_cache_key(file_sha, self.mode)
        if not no_cache:
            cached = cache.get(key)
            if cached and cached.get("result"):
                env = envelope.ok(
                    cached.get("task_type", "document_parsing"),
                    cached.get("tool_used", self.name),
                    cached["result"],
                    cached.get("confidence", "high"),
                    {**cached.get("metadata", {}), "cached": True},
                )
                return env, EXIT_OK

        t0 = time.time()
        try:
            batch_id, upload_url = _apply_upload_urls(token, p.name, model_version)
            with open(path, "rb") as f:
                up = requests.put(upload_url, data=f, timeout=120)
            if up.status_code != 200:
                raise MinerUError(
                    f"MinerU 文件上传失败 status={up.status_code}", EXIT_GENERIC
                )
            markdown = _poll_result(token, batch_id)
        except MinerUError as e:
            return (
                envelope.fail("document_parsing", result=str(e), code=e.code),
                e.code,
            )
        except requests.RequestException as e:
            return (
                envelope.fail(
                    "document_parsing", result=f"MinerU 网络错误: {e}", code=EXIT_NETWORK
                ),
                EXIT_NETWORK,
            )

        env = envelope.ok(
            "document_parsing",
            tool=f"mineru:{model_version}",
            result=markdown,
            confidence="high",
            metadata={
                "mode": self.mode,
                "model_version": model_version,
                "batch_id": batch_id,
                "latency_ms": int((time.time() - t0) * 1000),
                "cached": False,
            },
        )
        cache.put(key, env.to_dict())
        return env, EXIT_OK


def document_chain(file_path: str, cfg: Config, cache: Cache, no_cache: bool = False):
    """文档解析降级链：mineru-vlm(推荐) -> mineru-pipeline(默认管线回退)。

    .html/.htm 文件由 MinerUChannel 内部强制走 MinerU-HTML 管线，与 mode 无关。
    """
    from .base import Chain  # 延迟避免循环

    chain = Chain(
        [MinerUChannel("vlm"), MinerUChannel("pipeline")],
        task_type="document_parsing",
    )
    return chain.run(file_path, prompt="", cfg=cfg, cache=cache, no_cache=no_cache)

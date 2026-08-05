"""文档解析通道：MinerU 云端解析（flash -> extract）。

将 PDF/论文/报告/长文档解析为 Markdown。

MinerU API 流程（v4）：
  1. POST /api/v4/file-urls/batch 申请预签名上传地址（-> batch_id + file_urls）
  2. PUT 上传文件（系统自动触发解析任务）
  3. GET /api/v4/extract-results/batch/{batch_id} 轮询结果（-> markdown 下载地址）
  4. 下载 markdown

模型版本：vlm（多模态，含公式/表格）；flash 走轻量管线。
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Optional, Tuple

import requests

from .. import envelope
from ..config import load_config

EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_AUTH = 2
EXIT_NETWORK = 4

MINERU_BATCH_URL = "https://mineru.net/api/v4/file-urls/batch"
MINERU_RESULTS_URL = "https://mineru.net/api/v4/extract-results/batch/{batch_id}"


class MinerUError(Exception):
    def __init__(self, message: str, code: int = EXIT_GENERIC):
        super().__init__(message)
        self.code = code


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _apply_upload_urls(token: str, name: str, model_version: str) -> tuple[str, str]:
    """申请上传地址，返回 (batch_id, upload_url)。"""
    data = {"files": [{"name": name, "data_id": str(uuid.uuid4())}], "model_version": model_version}
    resp = requests.post(MINERU_BATCH_URL, headers=_headers(token), json=data, timeout=30)
    if resp.status_code in (401, 403):
        raise MinerUError("MinerU 认证失败", EXIT_AUTH)
    if resp.status_code != 200:
        raise MinerUError(f"MinerU 申请上传失败 status={resp.status_code}", EXIT_GENERIC)
    result = resp.json()
    if result.get("code") != 0:
        raise MinerUError(f"MinerU 申请上传失败: {result.get('msg') or result.get('message')}", EXIT_GENERIC)
    batch_id = result["data"]["batch_id"]
    upload_url = result["data"]["file_urls"][0]
    return batch_id, upload_url


def _poll_result(token: str, batch_id: str, timeout: int = 180) -> str:
    """轮询批量解析结果，返回 markdown 内容。

    MinerU v4 真实结构：
      data.extract_result[].state = running|done|failed
      data.extract_result[].full_zip_url = 结果 zip 包（含 .md）
    """
    import io
    import zipfile

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
                    f"MinerU 解析失败: {item.get('err_msg') or item.get('error')}", EXIT_GENERIC
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


def _download_markdown(zip_url: str) -> str:
    """从结果 zip 包中提取 markdown 文本。"""
    import io
    import zipfile

    resp = requests.get(zip_url, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        md_files = [n for n in zf.namelist() if n.endswith(".md")]
        if not md_files:
            raise MinerUError("MinerU 结果 zip 中无 markdown 文件", EXIT_GENERIC)
        return zf.read(md_files[0]).decode("utf-8", errors="ignore")


def mineru_extract(file_path: str, mode: str = "flash") -> Tuple[Optional[envelope.Envelope], int]:
    """调用 MinerU 解析文档。mode: flash | extract。"""
    token = load_config()["mineru_token"]
    if not token:
        return envelope.fail(
            "document_parsing", result="未配置 MINERU_TOKEN，文档解析不可用。"
        ), EXIT_AUTH

    path = Path(file_path)
    if not path.exists():
        return envelope.fail("document_parsing", result=f"文件不存在: {file_path}"), EXIT_GENERIC

    # 纯文本/简单 Markdown 直接读取，无需云端
    if path.suffix.lower() in (".md", ".txt"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        env = envelope.ok(
            "document_parsing",
            tool="local-text",
            result=text,
            confidence="high",
            metadata={"mode": "local-text", "latency_ms": 0},
        )
        return env, EXIT_OK

    t0 = time.time()
    model_version = "MinerU-HTML" if path.suffix.lower() == ".html" else "vlm"
    try:
        batch_id, upload_url = _apply_upload_urls(token, path.name, model_version)
        with open(path, "rb") as f:
            up = requests.put(upload_url, data=f, timeout=120)
        if up.status_code != 200:
            raise MinerUError(f"MinerU 文件上传失败 status={up.status_code}", EXIT_GENERIC)

        markdown = _poll_result(token, batch_id)
    except MinerUError as e:
        return envelope.fail("document_parsing", result=str(e)), e.code
    except requests.RequestException as e:
        return envelope.fail("document_parsing", result=f"MinerU 网络错误: {e}"), EXIT_NETWORK

    env = envelope.ok(
        "document_parsing",
        tool=f"mineru:{model_version}",
        result=markdown,
        confidence="high",
        metadata={
            "mode": mode,
            "batch_id": batch_id,
            "latency_ms": int((time.time() - t0) * 1000),
        },
    )
    return env, EXIT_OK


def document_chain(file_path: str) -> Tuple[envelope.Envelope, int]:
    """文档解析降级链：mineru flash -> mineru extract。"""
    attempts = []
    env, code = mineru_extract(file_path, "flash")
    attempts.append({"name": "mineru-flash", "code": code})
    if code == EXIT_OK and env.result:
        env.metadata["attempts"] = attempts
        return env, EXIT_OK

    env2, code2 = mineru_extract(file_path, "extract")
    attempts.append({"name": "mineru-extract", "code": code2})
    if code2 == EXIT_OK and env2.result:
        env2.metadata["attempts"] = attempts
        return env2, EXIT_OK

    return envelope.fail(
        "document_parsing", result=env.result or env2.result or "文档解析全部失败", attempts=attempts
    ), EXIT_GENERIC
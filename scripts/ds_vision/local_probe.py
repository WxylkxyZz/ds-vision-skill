"""本地视觉运行时探测。

单一事实来源：router 与 vlm 通道共用本模块，避免重复探测与脆弱的字符串解析。
URL 解析使用 ``urllib.parse``，端口探测使用 socket。
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlsplit


@dataclass
class LocalRuntime:
    name: str          # ollama / lmstudio / llamacpp
    base_url: str      # 规范化后的 chat/completions URL
    host: str
    port: int
    default_model: str


# 本地 OpenAI 兼容服务候选
LOCAL_RUNTIMES = (
    ("ollama",  "http://127.0.0.1:11434/v1/chat/completions", "qwen2.5-vl:3b"),
    ("lmstudio", "http://127.0.0.1:1234/v1/chat/completions", ""),
    ("llamacpp", "http://127.0.0.1:8080/v1/chat/completions", ""),
)


def port_open(host: str, port: int, timeout: float = 0.7) -> bool:
    """探测 TCP 端口是否开放。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def parse_host_port(url: str) -> Optional[tuple]:
    """从 URL 解析 (host, port)，失败返回 None。"""
    parts = urlsplit(url)
    host, port = parts.hostname, parts.port
    if host and port:
        return host, port
    return None


def probe_local_runtimes() -> List[LocalRuntime]:
    """探测本地运行时，返回可达运行时列表。"""
    found: List[LocalRuntime] = []
    for name, url, default_model in LOCAL_RUNTIMES:
        hp = parse_host_port(url)
        if not hp:
            continue
        host, port = hp
        if port_open(host, port):
            found.append(
                LocalRuntime(
                    name=name,
                    base_url=url,
                    host=host,
                    port=port,
                    default_model=default_model,
                )
            )
    return found

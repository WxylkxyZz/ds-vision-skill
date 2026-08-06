"""统一输出契约 (Envelope)。

所有通道输出同构结构，主模型 / 调用方只需读取 ``result`` 字段即可继续推理，
调试时才查看 ``metadata``。

confidence 约定：
- ``high``   云端通道成功 / 本地文本快捷 / 缓存命中
- ``medium`` 部分结果或兜底成功
- ``low``    完全失败
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

# 退出码（全通道共用）
EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_AUTH = 2
EXIT_RATE_LIMIT = 3
EXIT_NETWORK = 4
EXIT_REJECTED = 5

# 退出码 -> error_type 标签，写入 metadata 便于调试
_CODE_TO_ERROR_TYPE = {
    EXIT_OK: None,
    EXIT_GENERIC: "generic",
    EXIT_AUTH: "auth",
    EXIT_RATE_LIMIT: "rate_limit",
    EXIT_NETWORK: "network",
    EXIT_REJECTED: "rejected",
}


@dataclass
class Envelope:
    """统一视觉输出结构。

    Attributes:
        task_type: image_reasoning | document_parsing | ocr
        tool_used: 实际使用的通道或模型；失败时为最后尝试的通道名
        confidence: high | medium | low
        result: 识别 / 解析 / 理解后的内容（主模型读取字段）
        metadata: 附加信息（通道、耗时、缓存、尝试链、error_type 等）
    """

    task_type: str
    tool_used: str
    confidence: str
    result: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, ordering: bool = True) -> Dict[str, Any]:
        d = asdict(self)
        if ordering:
            return {
                "task_type": d["task_type"],
                "tool_used": d["tool_used"],
                "confidence": d["confidence"],
                "result": d["result"],
                "metadata": d["metadata"],
            }
        return d

    def to_json(self, ordering: bool = True) -> str:
        return json.dumps(
            self.to_dict(ordering), ensure_ascii=False, indent=2, default=str
        )

    def add_attempt(self, name: str, code: int, message: str = "") -> None:
        attempts = self.metadata.setdefault("attempts", [])
        attempts.append(
            {"name": name, "code": code, **({"message": message} if message else {})}
        )


def ok(
    task_type: str,
    tool: str,
    result: str,
    confidence: str = "high",
    metadata: Optional[Dict[str, Any]] = None,
) -> Envelope:
    return Envelope(
        task_type=task_type,
        tool_used=tool,
        confidence=confidence,
        result=result,
        metadata=metadata or {},
    )


def fail(
    task_type: str,
    result: str = "",
    confidence: str = "low",
    tool_source: str = "router",
    metadata: Optional[Dict[str, Any]] = None,
    attempts: Optional[List[Dict[str, Any]]] = None,
    code: int = EXIT_GENERIC,
) -> Envelope:
    """构造失败 Envelope。

    Args:
        tool_source: 失败来源通道名（默认 router，仅降级链为空时保留）。
        code: 退出码，用于派生 metadata.error_type。
    """
    meta = metadata or {}
    if attempts:
        meta["attempts"] = attempts
    err = _CODE_TO_ERROR_TYPE.get(code)
    if err and "error_type" not in meta:
        meta["error_type"] = err
    return Envelope(
        task_type=task_type,
        tool_used=tool_source,
        confidence=confidence,
        result=result,
        metadata=meta,
    )

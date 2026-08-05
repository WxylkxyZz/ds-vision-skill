"""统一输出契约 (Envelope)。

所有通道在 Json 模式下输出同构结构，主模型 / 调用方只需读取 ``result`` 字段
即可继续推理，调试时才查看 ``metadata``。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class Envelope:
    """统一视觉输出结构。

    Attributes:
        task_type: 任务类型 image_reasoning | document_parsing | ocr
        tool_used: 实际使用的通道或模型
        confidence: high | medium | low
        result: 识别 / 解析 / 理解后的内容
        metadata: 附加信息（通道、耗时、缓存、尝试链等）
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
        import json

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
    metadata: Optional[Dict[str, Any]] = None,
    attempts: Optional[List[Dict[str, Any]]] = None,
) -> Envelope:
    meta = metadata or {}
    if attempts:
        meta["attempts"] = attempts
    return Envelope(
        task_type=task_type,
        tool_used="router",
        confidence=confidence,
        result=result,
        metadata=meta,
    )
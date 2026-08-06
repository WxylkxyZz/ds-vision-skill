"""Envelope 单元测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ds_vision import envelope
from ds_vision.envelope import Envelope, EXIT_AUTH, EXIT_GENERIC, EXIT_NETWORK, EXIT_OK


def test_ok_basic():
    env = envelope.ok("image_reasoning", "glm:GLM-4V-Flash", "结果", "high")
    assert env.task_type == "image_reasoning"
    assert env.tool_used == "glm:GLM-4V-Flash"
    assert env.confidence == "high"
    assert env.result == "结果"


def test_fail_tool_source():
    """fail 的 tool_used 应反映来源通道，而非恒为 router。"""
    env = envelope.fail("image_reasoning", result="x", tool_source="glm", code=EXIT_AUTH)
    assert env.tool_used == "glm"
    assert env.metadata["error_type"] == "auth"


def test_fail_router_default():
    env = envelope.fail("ocr", result="y")
    assert env.tool_used == "router"  # 默认
    assert env.confidence == "low"
    assert env.metadata["error_type"] == "generic"


def test_fail_with_attempts():
    attempts = [{"name": "glm", "code": EXIT_AUTH}, {"name": "glm-thinking", "code": EXIT_NETWORK}]
    env = envelope.fail("image_reasoning", result="全失败", attempts=attempts, tool_source="glm-thinking")
    assert env.metadata["attempts"] == attempts
    assert env.tool_used == "glm-thinking"


def test_to_json_ordering():
    import json
    env = envelope.ok("ocr", "baidu-ocr", "文字", metadata={"latency_ms": 100})
    d = json.loads(env.to_json())
    assert list(d.keys()) == ["task_type", "tool_used", "confidence", "result", "metadata"]
    assert d["metadata"]["latency_ms"] == 100


def test_add_attempt():
    env = envelope.ok("ocr", "baidu-ocr", "文字")
    env.add_attempt("baidu-ocr", EXIT_OK)
    assert env.metadata["attempts"] == [{"name": "baidu-ocr", "code": EXIT_OK}]
    env.add_attempt("glm", EXIT_NETWORK, message="网络错误")
    assert env.metadata["attempts"][1] == {"name": "glm", "code": EXIT_NETWORK, "message": "网络错误"}

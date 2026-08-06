"""Cache 单元测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ds_vision.cache import Cache, document_cache_key, sha256_file, vlm_cache_key


def test_vlm_cache_key_stable():
    k1 = vlm_cache_key("abc", "prompt", "glm", "GLM-4V-Flash")
    k2 = vlm_cache_key("abc", "prompt", "glm", "GLM-4V-Flash")
    k3 = vlm_cache_key("abc", "prompt2", "glm", "GLM-4V-Flash")
    assert k1 == k2
    assert k1 != k3  # 不同 prompt 不同 key


def test_vlm_cache_key_channel_change():
    k1 = vlm_cache_key("abc", "p", "glm", "m")
    k2 = vlm_cache_key("abc", "p", "glm-thinking", "m")
    assert k1 != k2


def test_document_cache_key_distinct_mode():
    """flash 与 extract 的 key 不同（接入后才能区分缓存）。"""
    k1 = document_cache_key("abc", "flash")
    k2 = document_cache_key("abc", "extract")
    assert k1 != k2


def test_cache_get_put(tmp_cache):
    cache = tmp_cache
    key = "testkey"
    assert cache.get(key) is None
    cache.put(key, {"result": "hello", "tool_used": "glm"})
    got = cache.get(key)
    assert got["result"] == "hello"


def test_cache_missing_returns_none(tmp_cache):
    assert tmp_cache.get("nonexistent") is None


def test_sha256_file(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"hello")
    h = sha256_file(str(p))
    assert h == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

"""local_probe 单元测试：URL 解析、端口探测、探测列表。"""

import socket
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ds_vision.local_probe import (
    LOCAL_RUNTIMES,
    parse_host_port,
    port_open,
    probe_local_runtimes,
)


def test_parse_host_port_ollama():
    h, p = parse_host_port("http://127.0.0.1:11434/v1/chat/completions")
    assert h == "127.0.0.1"
    assert p == 11434


def test_parse_host_port_lmstudio():
    h, p = parse_host_port("http://127.0.0.1:1234/v1/chat/completions")
    assert p == 1234


def test_parse_host_port_invalid():
    assert parse_host_port("not a url") is None


def test_port_open_closed():
    # 1 是个通常没人监听的端口
    assert port_open("127.0.0.1", 1, timeout=0.3) is False


def test_probe_local_runtimes_empty(monkeypatch):
    monkeypatch.setattr("ds_vision.local_probe.port_open", lambda *a, **k: False)
    runtimes = probe_local_runtimes()
    assert runtimes == []


def test_probe_finds_ollama(monkeypatch):
    def fake_port_open(host, port, timeout=0.7):
        return port == 11434

    monkeypatch.setattr("ds_vision.local_probe.port_open", fake_port_open)
    runtimes = probe_local_runtimes()
    assert len(runtimes) == 1
    assert runtimes[0].name == "ollama"
    assert runtimes[0].port == 11434
    assert runtimes[0].default_model == "qwen2.5-vl:3b"


def test_probe_finds_multiple(monkeypatch):
    monkeypatch.setattr("ds_vision.local_probe.port_open", lambda *a, **k: True)
    runtimes = probe_local_runtimes()
    assert len(runtimes) == len(LOCAL_RUNTIMES)
    names = [r.name for r in runtimes]
    assert "ollama" in names and "lmstudio" in names and "llamacpp" in names

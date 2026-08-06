"""config 单元测试：get_env 无假作用域循环、load_dotenv、模型默认名、status_report。"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import inspect

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ds_vision import config
from ds_vision.config import (
    DEFAULT_GLM_FAST_MODEL,
    DEFAULT_GLM_THINKING_MODEL,
    Config,
    GLMConfig,
    get_env,
    load_config,
    load_dotenv,
)


def test_glm_model_renamed():
    """GLM 模型应改为 GLM-4V-Flash / glm-4.1v-thinking-flash。"""
    assert DEFAULT_GLM_FAST_MODEL == "GLM-4V-Flash"
    assert DEFAULT_GLM_THINKING_MODEL == "glm-4.1v-thinking-flash"
    g = GLMConfig()
    assert g.fast_model == "GLM-4V-Flash"
    assert g.thinking_model == "glm-4.1v-thinking-flash"


def test_get_env_no_scope_loop():
    """回归测试：get_env 不应再含 Process/User/Machine 三次循环。"""
    src = inspect.getsource(get_env)
    assert "Process" not in src
    assert "User" not in src
    assert "Machine" not in src
    # 单次 os.environ.get
    assert src.count("os.environ.get") == 1


def test_get_env_returns_default():
    os.environ.pop("DS_VISION_TEST_NONEXIST_VAR", None)
    assert get_env("DS_VISION_TEST_NONEXIST_VAR", "def") == "def"


def test_get_env_reads_existing(monkeypatch):
    monkeypatch.setenv("DS_VISION_TEST_VAR", "value123")
    assert get_env("DS_VISION_TEST_VAR") == "value123"


def test_load_dotenv_no_override(tmp_path):
    """已存在的环境变量不被 .env 覆盖。"""
    monkeypatch_key = "DS_VISION_TEST_DOTENV"
    os.environ[monkeypatch_key] = "existing"
    env_file = tmp_path / ".env"
    env_file.write_text(f"{monkeypatch_key}=fromfile\nDS_VISION_NEW=hello", encoding="utf-8")
    load_dotenv(env_file)
    assert os.environ[monkeypatch_key] == "existing"  # 不覆盖
    assert os.environ["DS_VISION_NEW"] == "hello"
    os.environ.pop(monkeypatch_key, None)
    os.environ.pop("DS_VISION_NEW", None)


def test_load_config_snapshot():
    cfg = load_config()
    assert isinstance(cfg, Config)
    assert isinstance(cfg.glm, GLMConfig)
    assert cfg.glm.fast_model == "GLM-4V-Flash"


def test_status_report_uses_probe(monkeypatch, cfg_factory):
    """status_report 的 local 字段应来自 probe_local_runtimes，而非硬编码 True。"""
    monkeypatch.setattr(
        "ds_vision.local_probe.probe_local_runtimes",
        lambda: [],
    )
    cfg = cfg_factory()
    report = config.status_report(cfg)
    assert report["local"] is False  # 探测为空 -> False
    assert report["local_runtimes"] == []
    assert report["glm"] is False

    monkeypatch.setattr(
        "ds_vision.local_probe.probe_local_runtimes",
        lambda: [type("R", (), {"name": "ollama"})()],
    )
    report = config.status_report(cfg)
    assert report["local"] is True
    assert "ollama" in report["local_runtimes"]

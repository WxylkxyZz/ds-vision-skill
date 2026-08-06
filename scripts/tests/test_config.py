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


def test_status_report_fields(cfg_factory):
    """status_report 反映各通道配置态（无 local 字段——本地视觉模型已移除）。"""
    cfg = cfg_factory()  # 全空
    report = config.status_report(cfg)
    assert report["glm"] is False
    assert report["glm_thinking"] is False
    assert report["custom"] is False
    assert report["baidu_ocr"] is False
    assert report["mineru"] is False
    # 本地视觉模型已移除，不再有 local / local_runtimes 字段
    assert "local" not in report
    assert "local_runtimes" not in report

    cfg2 = cfg_factory(glm_api_key="k", baidu_api_key="bk", baidu_secret_key="bs")
    report2 = config.status_report(cfg2)
    assert report2["glm"] is True
    assert report2["glm_thinking"] is True
    assert report2["baidu_ocr"] is True

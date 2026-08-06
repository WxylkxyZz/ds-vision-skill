"""共享 fixtures：临时缓存目录、mock requests、样本文件、Config 工厂。"""

import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys
import os

# 让 tests 能 import ds_vision 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ds_vision.config import Config, GLMConfig, BaiduOCRConfig
from ds_vision.cache import Cache


@pytest.fixture
def tmp_cache_dir(tmp_path):
    d = tmp_path / "cache"
    d.mkdir()
    return str(d)


@pytest.fixture
def tmp_cache(tmp_cache_dir):
    return Cache(tmp_cache_dir)


@pytest.fixture
def sample_image(tmp_path):
    """最小合法 PNG（1x1 红点）。"""
    png = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
        b"\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
        b"\x8d\xa5K-\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    p = tmp_path / "sample.png"
    p.write_bytes(png)
    return str(p)


@pytest.fixture
def sample_pdf(tmp_path):
    """最小合法 PDF 头。"""
    p = tmp_path / "sample.pdf"
    p.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF")
    return str(p)


@pytest.fixture
def sample_md(tmp_path):
    p = tmp_path / "sample.md"
    p.write_text("# 标题\n\n正文内容。", encoding="utf-8")
    return str(p)


@pytest.fixture
def cfg_factory(tmp_cache_dir):
    """构造 Config，字段可覆盖。"""

    def _make(
        glm_api_key="",
        custom_api_key="",
        custom_base_url="",
        custom_model="",
        baidu_api_key="",
        baidu_secret_key="",
        mineru_token="",
        local_model="",
    ):
        return Config(
            glm=GLMConfig(api_key=glm_api_key),
            custom=__import__(
                "ds_vision.config", fromlist=["CustomConfig"]
            ).CustomConfig(
                base_url=custom_base_url,
                api_key=custom_api_key,
                model=custom_model,
            ),
            baidu_ocr=BaiduOCRConfig(api_key=baidu_api_key, secret_key=baidu_secret_key),
            cache_dir=tmp_cache_dir,
            mineru_token=mineru_token,
            local_model=local_model,
        )

    return _make


def make_response(status_code=200, json_data=None, content=b""):
    """构造 mock requests.Response。"""
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    resp.content = content
    resp.raise_for_status.return_value = None
    return resp


@pytest.fixture
def make_resp():
    return make_response

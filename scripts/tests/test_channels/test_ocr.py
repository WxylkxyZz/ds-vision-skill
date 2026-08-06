"""OCR 通道测试（仅百度，Tesseract 已移除）。"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import ds_vision.channels.ocr as ocr_mod
from ds_vision.envelope import EXIT_AUTH, EXIT_OK
from ds_vision.channels.ocr import BaiduOCRChannel

POST = "ds_vision.channels.ocr.requests.post"
GET = "ds_vision.channels.ocr.requests.get"


def test_o1_baidu_success(sample_image, tmp_cache, cfg_factory, make_resp):
    cfg = cfg_factory(baidu_api_key="k", baidu_secret_key="s")
    ch = BaiduOCRChannel()
    with patch(GET, return_value=make_resp(200, {"access_token": "tok", "expires_in": 3600})), \
         patch(POST, return_value=make_resp(200, {"words_result": [{"words": "你好"}, {"words": "世界"}]})):
        env, code = ch.attempt(sample_image, prompt="", cfg=cfg, cache=tmp_cache, no_cache=True)
    assert code == EXIT_OK
    assert env.result == "你好\n世界"
    assert env.tool_used == "baidu-ocr"


def test_o2_baidu_401_no_tesseract(sample_image, tmp_cache, cfg_factory, make_resp):
    """百度 401 -> 失败信封（链结束，无 Tesseract）。"""
    cfg = cfg_factory(baidu_api_key="k", baidu_secret_key="s")
    ch = BaiduOCRChannel()
    with patch(GET, return_value=make_resp(200, {"access_token": "tok", "expires_in": 3600})), \
         patch(POST, return_value=make_resp(401)):
        env, code = ch.attempt(sample_image, prompt="", cfg=cfg, cache=tmp_cache, no_cache=True)
    assert code == EXIT_AUTH
    assert "认证失败" in env.result


def test_o3_empty_words_result_low_conf(sample_image, tmp_cache, cfg_factory, make_resp):
    """空 words_result -> confidence=low，视为失败（Chain 不接受）。"""
    cfg = cfg_factory(baidu_api_key="k", baidu_secret_key="s")
    ch = BaiduOCRChannel()
    with patch(GET, return_value=make_resp(200, {"access_token": "tok", "expires_in": 3600})), \
         patch(POST, return_value=make_resp(200, {"words_result": []})):
        env, code = ch.attempt(sample_image, prompt="", cfg=cfg, cache=tmp_cache, no_cache=True)
    assert code == EXIT_OK
    assert env.result == ""
    assert env.confidence == "low"


def test_o4_accurate_uses_endpoint(sample_image, tmp_cache, cfg_factory, make_resp):
    cfg = cfg_factory(baidu_api_key="k", baidu_secret_key="s")
    ch = BaiduOCRChannel(accurate=True)
    with patch(GET, return_value=make_resp(200, {"access_token": "tok", "expires_in": 3600})), \
         patch(POST, return_value=make_resp(200, {"words_result": [{"words": "x"}]})) as mp:
        ch.attempt(sample_image, prompt="", cfg=cfg, cache=tmp_cache, no_cache=True)
    url = mp.call_args.args[0]
    assert "accurate_basic" in url


def test_o5_general_uses_endpoint(sample_image, tmp_cache, cfg_factory, make_resp):
    cfg = cfg_factory(baidu_api_key="k", baidu_secret_key="s")
    ch = BaiduOCRChannel(accurate=False)
    with patch(GET, return_value=make_resp(200, {"access_token": "tok", "expires_in": 3600})), \
         patch(POST, return_value=make_resp(200, {"words_result": [{"words": "x"}]})) as mp:
        ch.attempt(sample_image, prompt="", cfg=cfg, cache=tmp_cache, no_cache=True)
    assert "general_basic" in mp.call_args.args[0]


def test_o6_no_tesseract_regression():
    """回归：tesseract_ocr 函数与 pytesseract 导入应不存在。"""
    import inspect

    assert not hasattr(ocr_mod, "tesseract_ocr"), "tesseract_ocr 应已移除"
    src = inspect.getsource(ocr_mod)
    assert "pytesseract" not in src, "pytesseract 导入应已移除"
    assert "tesseract" not in src.lower(), "tesseract 提及应已移除"


def test_o7_missing_config_auth(sample_image, tmp_cache, cfg_factory):
    cfg = cfg_factory(baidu_api_key="", baidu_secret_key="")
    ch = BaiduOCRChannel()
    env, code = ch.attempt(sample_image, prompt="", cfg=cfg, cache=tmp_cache, no_cache=True)
    assert code == EXIT_AUTH

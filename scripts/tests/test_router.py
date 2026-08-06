"""router 路由 + 降级链合并测试。"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ds_vision.cache import Cache
from ds_vision.router import route


def test_r1_auto_png_reason(sample_image, tmp_cache_dir, cfg_factory):
    """auto + .png -> reason 意图（走 VLM）。"""
    cfg = cfg_factory(glm_api_key="k")
    cache = Cache(tmp_cache_dir)
    with patch("ds_vision.channels.vlm.requests.post") as mp:
        from unittest.mock import MagicMock
        mp.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"choices": [{"message": {"content": "图描述"}}]}),
        )
        env, code = route(sample_image, prompt="描述", cfg=cfg, cache=cache, no_cache=True)
    assert code == 0
    assert env.result == "图描述"


def test_r2_auto_pdf_document(sample_md, tmp_cache_dir, cfg_factory):
    """auto + .md -> document 意图，本地文本快捷。"""
    cfg = cfg_factory()
    cache = Cache(tmp_cache_dir)
    env, code = route(sample_md, prompt="", cfg=cfg, cache=cache)
    assert code == 0
    assert env.tool_used == "local-text"


def test_r3_auto_png_ocr_intent(sample_image, tmp_cache_dir, cfg_factory):
    """auto + .png + prompt 含 OCR -> ocr 意图。"""
    cfg = cfg_factory(baidu_api_key="k", baidu_secret_key="s")
    cache = Cache(tmp_cache_dir)
    from unittest.mock import MagicMock
    token_resp = MagicMock(status_code=200, json=MagicMock(return_value={"access_token": "t", "expires_in": 3600}))
    ocr_resp = MagicMock(status_code=200, json=MagicMock(return_value={"words_result": [{"words": "OCR结果"}]}))
    with patch("ds_vision.channels.ocr.requests.get", return_value=token_resp), \
         patch("ds_vision.channels.ocr.requests.post", return_value=ocr_resp):
        env, code = route(sample_image, prompt="请 OCR 提取文字", cfg=cfg, cache=cache, no_cache=True)
    assert code == 0
    assert env.result == "OCR结果"
    assert env.task_type == "ocr"


def test_r5_ocr_fail_fallback_vlm(sample_image, tmp_cache_dir, cfg_factory):
    """OCR 失败 -> 退回 VLM，attempts 合并两链。"""
    cfg = cfg_factory(glm_api_key="k")  # 无百度 key -> OCR 直接失败
    cache = Cache(tmp_cache_dir)
    from unittest.mock import MagicMock
    vlm_resp = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"choices": [{"message": {"content": "视觉兜底"}}]}),
    )
    with patch("ds_vision.channels.vlm.requests.post", return_value=vlm_resp):
        env, code = route(sample_image, prompt="OCR 文字", intent="ocr", cfg=cfg, cache=cache, no_cache=True)
    assert code == 0
    assert env.result == "视觉兜底"
    # attempts 应包含 baidu-ocr(失败) + glm(成功)
    names = [a["name"] for a in env.metadata["attempts"]]
    assert "baidu-ocr" in names
    assert "glm" in names


def test_r6_file_not_found(tmp_cache_dir, cfg_factory):
    """文件不存在 -> 退出码 1。"""
    cfg = cfg_factory()
    cache = Cache(tmp_cache_dir)
    env, code = route("nonexistent.png", cfg=cfg, cache=cache)
    assert code == 1
    assert "not found" in env.result.lower()


def test_r7_no_config_all_fail(sample_image, tmp_cache_dir, cfg_factory):
    """无任何 key 调图片 -> 全失败，tool_used 为最后通道名（非 router）。"""
    cfg = cfg_factory()  # 全空
    cache = Cache(tmp_cache_dir)
    env, code = route(sample_image, prompt="p", cfg=cfg, cache=cache, no_cache=True)
    assert code != 0
    # 链中至少有 glm / glm-thinking 尝试
    assert env.metadata.get("attempts")
    # tool_used 不应是 "router"（除非链空），应是最后尝试的通道
    if env.metadata["attempts"]:
        assert env.tool_used == env.metadata["attempts"][-1]["name"]


def test_r8_complex_uses_thinking_first(sample_image, tmp_cache_dir, cfg_factory):
    """complex_=True -> 首通道 glm-thinking。"""
    cfg = cfg_factory(glm_api_key="k")
    cache = Cache(tmp_cache_dir)
    from unittest.mock import MagicMock
    vlm_resp = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"choices": [{"message": {"content": "thinking 结果"}}]}),
    )
    with patch("ds_vision.channels.vlm.requests.post", return_value=vlm_resp):
        env, code = route(sample_image, prompt="p", complex_=True, cfg=cfg, cache=cache, no_cache=True)
    assert code == 0
    assert env.tool_used.startswith("glm-thinking:")
    assert env.metadata["attempts"][0]["name"] == "glm-thinking"

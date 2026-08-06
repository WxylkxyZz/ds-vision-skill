"""VLM 通道 + 降级链测试（mock requests，不打真实 API）。"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ds_vision.envelope import EXIT_AUTH, EXIT_NETWORK, EXIT_OK
from ds_vision.local_probe import LocalRuntime
from ds_vision.channels.base import Chain
from ds_vision.channels.vlm import VLMChannel

POST = "ds_vision.channels.vlm.requests.post"


def test_v1_glm_success(sample_image, tmp_cache, cfg_factory, make_resp):
    """GLM 成功 -> tool_used=glm:GLM-4V-Flash，请求体含正确模型。"""
    cfg = cfg_factory(glm_api_key="k")
    ch = VLMChannel("glm")
    with patch(POST) as mock_post:
        mock_post.return_value = make_resp(
            200, {"choices": [{"message": {"content": "这是一只猫"}}]}
        )
        env, code = ch.attempt(
            sample_image, prompt="描述", cfg=cfg, cache=tmp_cache, no_cache=True
        )
    assert code == EXIT_OK
    assert env.result == "这是一只猫"
    assert env.tool_used == "glm:GLM-4V-Flash"
    body = mock_post.call_args.kwargs["json"]
    assert body["model"] == "GLM-4V-Flash"
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer k"


def test_v2_glm_401_degrades_to_thinking(sample_image, tmp_cache, cfg_factory, make_resp):
    """GLM 401 -> 降级 glm-thinking 成功。"""
    cfg = cfg_factory(glm_api_key="k")
    chain = Chain(
        [VLMChannel("glm"), VLMChannel("glm-thinking")], task_type="image_reasoning"
    )
    responses = [
        make_resp(401),
        make_resp(200, {"choices": [{"message": {"content": "thinking 结果"}}]}),
    ]
    with patch(POST, side_effect=responses) as mock_post:
        env, code = chain.run(
            sample_image, prompt="p", cfg=cfg, cache=tmp_cache, no_cache=True
        )
    assert code == EXIT_OK
    assert env.result == "thinking 结果"
    assert env.tool_used == "glm-thinking:glm-4.1v-thinking-flash"
    assert len(env.metadata["attempts"]) == 2
    assert mock_post.call_count == 2


def test_v3_all_cloud_fail_local_ok(sample_image, tmp_cache, cfg_factory, make_resp):
    """全云端失败 -> 本地探测 mock 开 -> 本地成功。"""
    cfg = cfg_factory(glm_api_key="k", local_model="qwen2.5-vl:3b")
    runtime = LocalRuntime("ollama", "http://127.0.0.1:11434/v1/chat/completions", "127.0.0.1", 11434, "qwen2.5-vl:3b")
    chain = Chain(
        [VLMChannel("glm"), VLMChannel("local", runtime=runtime)],
        task_type="image_reasoning",
    )
    responses = [
        make_resp(429),  # glm 限流
        make_resp(200, {"choices": [{"message": {"content": "本地结果"}}]}),
    ]
    with patch(POST, side_effect=responses):
        env, code = chain.run(
            sample_image, prompt="p", cfg=cfg, cache=tmp_cache, no_cache=True
        )
    assert code == EXIT_OK
    assert env.result == "本地结果"
    assert env.tool_used == "local:qwen2.5-vl:3b"


def test_v4_all_fail_envelope(sample_image, tmp_cache, cfg_factory, make_resp):
    """所有通道失败 -> 失败 Envelope，tool_used 为最后通道名（非 router）。"""
    cfg = cfg_factory(glm_api_key="k")
    chain = Chain([VLMChannel("glm"), VLMChannel("glm-thinking")], task_type="image_reasoning")
    with patch(POST, side_effect=[make_resp(401), make_resp(429)]):
        env, code = chain.run(
            sample_image, prompt="p", cfg=cfg, cache=tmp_cache, no_cache=True
        )
    assert code != EXIT_OK
    assert env.tool_used == "glm-thinking"  # 最后尝试的通道
    assert len(env.metadata["attempts"]) == 2


def test_v5_cache_hit_no_http(sample_image, tmp_cache, cfg_factory, make_resp):
    """缓存命中 -> 不发 HTTP，metadata.cached=True。"""
    cfg = cfg_factory(glm_api_key="k")
    ch = VLMChannel("glm")
    # 第一次调用填充缓存
    with patch(POST, return_value=make_resp(200, {"choices": [{"message": {"content": "缓存结果"}}]})):
        ch.attempt(sample_image, prompt="p", cfg=cfg, cache=tmp_cache, no_cache=True)
    # 第二次应命中缓存
    with patch(POST) as mock_post:
        env, code = ch.attempt(sample_image, prompt="p", cfg=cfg, cache=tmp_cache, no_cache=False)
    assert code == EXIT_OK
    assert env.result == "缓存结果"
    assert env.metadata["cached"] is True
    assert mock_post.call_count == 0


def test_v6_no_cache_forces_http(sample_image, tmp_cache, cfg_factory, make_resp):
    """--no-cache 即使有缓存也调 HTTP。"""
    cfg = cfg_factory(glm_api_key="k")
    ch = VLMChannel("glm")
    with patch(POST, return_value=make_resp(200, {"choices": [{"message": {"content": "首次"}}]})):
        ch.attempt(sample_image, prompt="p", cfg=cfg, cache=tmp_cache, no_cache=True)
    with patch(POST, return_value=make_resp(200, {"choices": [{"message": {"content": "再次"}}]})) as mp:
        env, code = ch.attempt(sample_image, prompt="p", cfg=cfg, cache=tmp_cache, no_cache=True)
    assert env.result == "再次"
    assert mp.call_count == 1


def test_v7_image_too_large(tmp_path, tmp_cache, cfg_factory, make_resp):
    """图片 > 15MB -> 立即失败，无 HTTP。"""
    big = tmp_path / "big.png"
    big.write_bytes(b"x" * (16 * 1024 * 1024))  # 16MB
    cfg = cfg_factory(glm_api_key="k")
    ch = VLMChannel("glm")
    with patch(POST) as mp:
        env, code = ch.attempt(str(big), prompt="p", cfg=cfg, cache=tmp_cache, no_cache=True)
    assert code != EXIT_OK
    assert "过大" in env.result
    assert mp.call_count == 0


def test_v8_complex_starts_with_thinking(sample_image, tmp_cache, cfg_factory, make_resp):
    """complex_=True -> 序以 glm-thinking 开头（由 router 的 Chain 构造体现，这里直接测通道）。"""
    cfg = cfg_factory(glm_api_key="k")
    ch = VLMChannel("glm-thinking")
    with patch(POST, return_value=make_resp(200, {"choices": [{"message": {"content": "thinking"}}]})):
        env, code = ch.attempt(sample_image, prompt="p", cfg=cfg, cache=tmp_cache, no_cache=True)
    assert code == EXIT_OK
    assert env.tool_used == "glm-thinking:glm-4.1v-thinking-flash"


def test_v9_missing_api_key_auth(sample_image, tmp_cache, cfg_factory, make_resp):
    """缺 API Key -> EXIT_AUTH。"""
    cfg = cfg_factory(glm_api_key="")
    ch = VLMChannel("glm")
    with patch(POST) as mp:
        env, code = ch.attempt(sample_image, prompt="p", cfg=cfg, cache=tmp_cache, no_cache=True)
    assert code == EXIT_AUTH
    assert mp.call_count == 0

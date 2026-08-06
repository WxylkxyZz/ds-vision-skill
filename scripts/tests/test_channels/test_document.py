"""文档解析通道测试（MinerU + 本地文本快捷）。

MinerU 一次解析的调用序列：
  POST batch(申请上传) -> PUT(上传文件) -> GET(轮询 done) -> GET(下载 zip)

model_version 经官方文档(https://mineru.net/apiManage/docs)核实：
  非HTML文件可选 pipeline(默认)/vlm(推荐)；HTML文件须指定 MinerU-HTML。
"""

import io
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ds_vision.envelope import EXIT_AUTH, EXIT_OK
from ds_vision.channels.document import (
    MODE_TO_MODEL_VERSION,
    MinerUChannel,
    MinerUError,
)

POST = "ds_vision.channels.document.requests.post"
GET = "ds_vision.channels.document.requests.get"
PUT = "ds_vision.channels.document.requests.put"


def _mock(status, json_data=None, content=b""):
    r = MagicMock()
    r.status_code = status
    r.content = content
    if json_data is not None:
        r.json.return_value = json_data
    r.raise_for_status.return_value = None
    return r


def _make_zip(text: str) -> bytes:
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zf:
        zf.writestr("out.md", text)
    return zbuf.getvalue()


def _batch_resp():
    return (200, {"code": 0, "data": {"batch_id": "bid1", "file_urls": ["http://upload"]}})


def _poll_done_resp():
    return (200, {"code": 0, "data": {"extract_result": [{"state": "done", "full_zip_url": "http://zip"}]}})


def _wire_get(mock_get, zip_bytes):
    """让 GET 顺序返回：轮询 done(json) -> 下载 zip(content)。"""
    mock_get.side_effect = [_mock(*_poll_done_resp()), _mock(200, content=zip_bytes)]


def test_d1_vlm_success(sample_pdf, tmp_cache, cfg_factory):
    """vlm 成功 -> model_version=vlm，tool_used=mineru:vlm。"""
    cfg = cfg_factory(mineru_token="tok")
    ch = MinerUChannel("vlm")
    zip_bytes = _make_zip("# 解析结果\n正文")

    with patch(POST, return_value=_mock(*_batch_resp())) as mp_post, \
         patch(PUT, return_value=_mock(200)), \
         patch(GET) as mg:
        _wire_get(mg, zip_bytes)
        env, code = ch.attempt(sample_pdf, prompt="", cfg=cfg, cache=tmp_cache, no_cache=True)

    assert code == EXIT_OK
    assert "解析结果" in env.result
    assert env.tool_used == "mineru:vlm"
    apply_body = mp_post.call_args.kwargs["json"]
    assert apply_body["model_version"] == "vlm"


def test_d11_regression_vlm_pipeline_different_model_version():
    """回归：vlm 与 pipeline 的 model_version 不同（降级有意义，非假降级）。"""
    assert MODE_TO_MODEL_VERSION["vlm"] != MODE_TO_MODEL_VERSION["pipeline"]
    assert MODE_TO_MODEL_VERSION["vlm"] == "vlm"
    assert MODE_TO_MODEL_VERSION["pipeline"] == "pipeline"


def test_d11_regression_channels_send_different(cfg_factory, sample_pdf, tmp_cache):
    """实际调用：vlm 与 pipeline 两次 batch 请求体 model_version 不同。"""
    cfg = cfg_factory(mineru_token="tok")
    zip_bytes = _make_zip("md content")
    sent = []

    real_batch = _mock(*_batch_resp())

    def post_side(*a, **kw):
        body = kw.get("json", {})
        if "model_version" in body:
            sent.append(body["model_version"])
        return real_batch

    for mode in ("vlm", "pipeline"):
        ch = MinerUChannel(mode)
        with patch(POST, side_effect=post_side), \
             patch(PUT, return_value=_mock(200)), \
             patch(GET) as mg:
            _wire_get(mg, zip_bytes)
            ch.attempt(sample_pdf, prompt="", cfg=cfg, cache=tmp_cache, no_cache=True)

    assert sent == ["vlm", "pipeline"]
    assert sent[0] != sent[1]


def test_d2_html_forces_mineru_html(tmp_path, tmp_cache, cfg_factory):
    """官方文档要求：.html 文件 model_version 须为 MinerU-HTML（与 mode 无关）。"""
    html = tmp_path / "page.html"
    html.write_text("<html><body>hi</body></html>", encoding="utf-8")
    cfg = cfg_factory(mineru_token="tok")
    ch = MinerUChannel("vlm")
    zip_bytes = _make_zip("# html 解析结果")

    with patch(POST, return_value=_mock(*_batch_resp())) as mp_post, \
         patch(PUT, return_value=_mock(200)), \
         patch(GET) as mg:
        _wire_get(mg, zip_bytes)
        env, code = ch.attempt(str(html), prompt="", cfg=cfg, cache=tmp_cache, no_cache=True)

    assert code == EXIT_OK
    apply_body = mp_post.call_args.kwargs["json"]
    assert apply_body["model_version"] == "MinerU-HTML"
    assert env.tool_used == "mineru:MinerU-HTML"


def test_d4_md_local_text_no_http(sample_md, tmp_cache, cfg_factory):
    """.md -> 本地文本快捷，无 HTTP，tool_used=local-text。"""
    cfg = cfg_factory(mineru_token="")  # 无 token 也应走快捷
    ch = MinerUChannel("vlm")
    with patch(POST) as mp, patch(GET) as mg:
        env, code = ch.attempt(sample_md, prompt="", cfg=cfg, cache=tmp_cache, no_cache=True)
    assert code == EXIT_OK
    assert env.tool_used == "local-text"
    assert "标题" in env.result
    assert mp.call_count == 0
    assert mg.call_count == 0


def test_d5_txt_local_text(tmp_path, tmp_cache, cfg_factory):
    """.txt -> 本地文本快捷。"""
    p = tmp_path / "note.txt"
    p.write_text("plain text note", encoding="utf-8")
    cfg = cfg_factory(mineru_token="")
    ch = MinerUChannel("vlm")
    with patch(POST) as mp:
        env, code = ch.attempt(str(p), prompt="", cfg=cfg, cache=tmp_cache, no_cache=True)
    assert code == EXIT_OK
    assert env.result == "plain text note"
    assert mp.call_count == 0


def test_d7_missing_token_auth(sample_pdf, tmp_cache, cfg_factory):
    """MINERU_TOKEN 缺失（非 .md/.txt）-> EXIT_AUTH。"""
    cfg = cfg_factory(mineru_token="")
    ch = MinerUChannel("vlm")
    env, code = ch.attempt(sample_pdf, prompt="", cfg=cfg, cache=tmp_cache, no_cache=True)
    assert code == EXIT_AUTH


def test_d8_poll_timeout(sample_pdf, tmp_cache, cfg_factory):
    """轮询超时 -> MinerUError 转失败 Envelope。"""
    cfg = cfg_factory(mineru_token="tok")
    ch = MinerUChannel("vlm")
    with patch(POST, return_value=_mock(*_batch_resp())), \
         patch(PUT, return_value=_mock(200)), \
         patch("ds_vision.channels.document._poll_result", side_effect=MinerUError("MinerU 解析超时", 1)):
        env, code = ch.attempt(sample_pdf, prompt="", cfg=cfg, cache=tmp_cache, no_cache=True)
    assert code != EXIT_OK
    assert "超时" in env.result


def test_d9_zip_no_markdown(sample_pdf, tmp_cache, cfg_factory):
    """结果 zip 无 .md 文件 -> 错误。"""
    cfg = cfg_factory(mineru_token="tok")
    ch = MinerUChannel("vlm")
    empty_zip = io.BytesIO()
    with zipfile.ZipFile(empty_zip, "w") as zf:
        zf.writestr("data.json", "{}")  # 无 .md
    zip_bytes = empty_zip.getvalue()

    with patch(POST, return_value=_mock(*_batch_resp())), \
         patch(PUT, return_value=_mock(200)), \
         patch(GET) as mg:
        _wire_get(mg, zip_bytes)
        env, code = ch.attempt(sample_pdf, prompt="", cfg=cfg, cache=tmp_cache, no_cache=True)
    assert code != EXIT_OK
    assert "markdown" in env.result


def test_d_document_cache_hit(sample_pdf, tmp_cache, cfg_factory):
    """document_cache_key 接入：缓存命中免 HTTP。"""
    cfg = cfg_factory(mineru_token="tok")
    ch = MinerUChannel("vlm")
    zip_bytes = _make_zip("缓存内容")

    # 第一次填充缓存
    with patch(POST, return_value=_mock(*_batch_resp())), \
         patch(PUT, return_value=_mock(200)), \
         patch(GET) as mg:
        _wire_get(mg, zip_bytes)
        ch.attempt(sample_pdf, prompt="", cfg=cfg, cache=tmp_cache, no_cache=True)

    # 第二次命中缓存，无 HTTP
    with patch(POST) as mp, patch(PUT), patch(GET) as mg:
        env, code = ch.attempt(sample_pdf, prompt="", cfg=cfg, cache=tmp_cache, no_cache=False)
    assert code == EXIT_OK
    assert env.result == "缓存内容"
    assert env.metadata["cached"] is True
    assert mp.call_count == 0
    assert mg.call_count == 0


def test_document_chain_helper(sample_pdf, tmp_cache, cfg_factory):
    """document_chain 便捷函数：vlm 成功即止。"""
    from ds_vision.channels.document import document_chain

    cfg = cfg_factory(mineru_token="tok")
    zip_bytes = _make_zip("chain ok")
    with patch(POST, return_value=_mock(*_batch_resp())), \
         patch(PUT, return_value=_mock(200)), \
         patch(GET) as mg:
        _wire_get(mg, zip_bytes)
        env, code = document_chain(sample_pdf, cfg, tmp_cache, no_cache=True)
    assert code == EXIT_OK
    assert env.result == "chain ok"
    assert len(env.metadata["attempts"]) == 1

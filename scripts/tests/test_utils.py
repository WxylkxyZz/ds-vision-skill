"""utils 单元测试：意图判断、文件类型、base64。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ds_vision.utils import (
    DOCUMENT_EXTS,
    IMAGE_EXTS,
    encode_image_base64,
    guess_intent,
    is_image,
    is_local_text,
)


def test_guess_intent_pdf_document():
    assert guess_intent(".pdf", "分析") == "document"
    assert guess_intent(".docx", "") == "document"


def test_guess_intent_image_reason():
    assert guess_intent(".png", "描述这张图") == "reason"
    assert guess_intent(".jpg", "what is this") == "reason"


def test_guess_intent_image_ocr_keyword():
    assert guess_intent(".png", "请 OCR 提取文字") == "ocr"
    assert guess_intent(".png", "识别发票") == "ocr"
    assert guess_intent(".jpeg", "extract text") == "ocr"


def test_guess_intent_unknown_defaults_document():
    assert guess_intent(".xyz", "") == "document"


def test_is_image():
    assert is_image("a.png") is True
    assert is_image("a.PDF") is False


def test_is_local_text():
    assert is_local_text("a.md") is True
    assert is_local_text("a.txt") is True
    assert is_local_text("a.pdf") is False


def test_encode_image_base64(sample_image):
    data = encode_image_base64(sample_image)
    assert data.startswith("data:image/png;base64,")


def test_image_exts_contains_common():
    for e in (".png", ".jpg", ".jpeg", ".webp"):
        assert e in IMAGE_EXTS


def test_document_exts_contains_md_txt():
    for e in (".pdf", ".md", ".txt"):
        assert e in DOCUMENT_EXTS

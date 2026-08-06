"""通用工具函数：意图判断、文件类型、base64 编码、大小。

本地运行时端口探测见 :mod:`ds_vision.local_probe`。
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

# 常见图片扩展名
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
# 常见文档扩展名
DOCUMENT_EXTS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".md", ".txt", ".html", ".htm"}
# 纯文本快捷扩展名（document 通道直接本地读取，不触云）
LOCAL_TEXT_EXTS = {".md", ".txt"}

# 提示词中触发 OCR 意图的关键词
OCR_KEYWORDS = (
    "ocr",
    "文字",
    "识别",
    "提取",
    "票据",
    "发票",
    "扫描",
    "截图文字",
    "text",
    "extract text",
)


def guess_intent(ext: str, prompt: str) -> str:
    """根据扩展名和提示词自动判断任务类型。"""
    ext = (ext or "").lower()
    if ext in DOCUMENT_EXTS:
        return "document"
    if ext in IMAGE_EXTS:
        low = prompt.lower()
        if any(k in low or k in prompt for k in OCR_KEYWORDS):
            return "ocr"
        return "reason"
    return "document"


def is_image(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTS


def is_document(path: str) -> bool:
    return Path(path).suffix.lower() in DOCUMENT_EXTS


def is_local_text(path: str) -> bool:
    return Path(path).suffix.lower() in LOCAL_TEXT_EXTS


def encode_image_base64(path: str) -> str:
    data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    mime = mimetypes.guess_type(path)[0] or "image/png"
    return f"data:{mime};base64,{data}"


def file_size_mb(path: str) -> float:
    return Path(path).stat().st_size / (1 << 20)

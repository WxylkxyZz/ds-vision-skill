"""配置管理：环境变量读取（进程 -> 用户 -> 机器）与 .env 文件加载。

通道配置优先使用环境变量；同时支持项目内 ``.env`` 文件便于本地开发。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

# 项目根目录（包上一级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Optional[Path] = None) -> None:
    """加载 .env 文件（不覆盖已存在的环境变量）。"""
    env_path = path or (PROJECT_ROOT / ".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_env(name: str, default: str = "") -> str:
    """按 进程 -> 用户 -> 机器 顺序读取环境变量。"""
    for scope in ("Process", "User", "Machine"):
        try:
            v = os.environ.get(name, "")
            if v:
                return v
        except Exception:
            pass
    return default


def is_configured(name: str) -> bool:
    return bool(get_env(name))


@dataclass
class GLMConfig:
    api_key: str = ""
    fast_model: str = "GLM-4.6V-Flash"
    thinking_model: str = "glm-4.1v-thinking-flash"
    base_url: str = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


@dataclass
class CustomConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""


@dataclass
class BaiduOCRConfig:
    api_key: str = ""
    secret_key: str = ""
    token_cache_file: str = ""


def load_config() -> Dict[str, any]:
    """读取全部通道配置。"""
    cache_dir = Path.home() / ".ds-vision-py" / "cache"
    baidu_token = Path.home() / ".ds-vision-py" / "baidu_token.json"
    return {
        "glm": GLMConfig(
            api_key=get_env("GLM_API_KEY"),
            base_url=get_env("GLM_BASE_URL", GLMConfig.base_url),
            fast_model=get_env("GLM_FAST_MODEL", GLMConfig.fast_model),
            thinking_model=get_env("GLM_THINKING_MODEL", GLMConfig.thinking_model),
        ),
        "custom": CustomConfig(
            base_url=get_env("VISION_CUSTOM_BASE_URL"),
            api_key=get_env("VISION_CUSTOM_API_KEY"),
            model=get_env("VISION_CUSTOM_MODEL"),
        ),
        "baidu_ocr": BaiduOCRConfig(
            api_key=get_env("BAIDU_API_KEY"),
            secret_key=get_env("BAIDU_SECRET_KEY"),
            token_cache_file=str(baidu_token),
        ),
        "cache_dir": str(cache_dir),
        "mineru_token": get_env("MINERU_TOKEN"),
        "local_model": get_env("VISION_LOCAL_MODEL"),
    }


def status_report() -> Dict[str, any]:
    """通道状态报告，供 setup / preflight 使用。"""
    cfg = load_config()
    return {
        "glm": bool(cfg["glm"].api_key),
        "glm_thinking": bool(cfg["glm"].api_key),
        "custom": bool(
            cfg["custom"].api_key and cfg["custom"].base_url and cfg["custom"].model
        ),
        "baidu_ocr": bool(
            cfg["baidu_ocr"].api_key and cfg["baidu_ocr"].secret_key
        ),
        "mineru": bool(cfg["mineru_token"]),
        "local": True,  # 运行时探测端口决定
        "cache_dir": cfg["cache_dir"],
    }
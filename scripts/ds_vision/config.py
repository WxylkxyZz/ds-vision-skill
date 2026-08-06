"""配置管理：环境变量读取与 .env 文件加载。

通道配置使用环境变量；同时支持项目内 ``.env`` 文件便于本地开发。
``Config`` 是一次解析的不可变快照，显式注入到通道，避免反复读取。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

# 项目根目录（ds_vision 包上一级，即 skill 根目录）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# GLM 默认模型（图像理解 / 视觉推理）
DEFAULT_GLM_FAST_MODEL = "GLM-4V-Flash"
DEFAULT_GLM_THINKING_MODEL = "glm-4.1v-thinking-flash"
DEFAULT_GLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

# 缓存与 token 位置
CACHE_DIR = str(Path.home() / ".ds-vision-py" / "cache")
BAIDU_TOKEN_FILE = str(Path.home() / ".ds-vision-py" / "baidu_token.json")


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
    """读取环境变量。

    Python 进程启动时已合并进程/用户/机器环境，单次读取即可，
    无需多作用域循环。
    """
    return os.environ.get(name, default)


def is_configured(name: str) -> bool:
    return bool(get_env(name))


@dataclass
class GLMConfig:
    api_key: str = ""
    fast_model: str = DEFAULT_GLM_FAST_MODEL
    thinking_model: str = DEFAULT_GLM_THINKING_MODEL
    base_url: str = DEFAULT_GLM_BASE_URL


@dataclass
class CustomConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""


@dataclass
class BaiduOCRConfig:
    api_key: str = ""
    secret_key: str = ""
    token_cache_file: str = BAIDU_TOKEN_FILE


@dataclass
class Config:
    """一次解析的通道配置快照，显式注入通道。"""

    glm: GLMConfig = field(default_factory=GLMConfig)
    custom: CustomConfig = field(default_factory=CustomConfig)
    baidu_ocr: BaiduOCRConfig = field(default_factory=BaiduOCRConfig)
    cache_dir: str = CACHE_DIR
    mineru_token: str = ""
    local_model: str = ""


def load_config() -> Config:
    """读取全部通道配置，返回不可变快照。仅在入口调用一次。"""
    return Config(
        glm=GLMConfig(
            api_key=get_env("GLM_API_KEY"),
            base_url=get_env("GLM_BASE_URL", DEFAULT_GLM_BASE_URL),
            fast_model=get_env("GLM_FAST_MODEL", DEFAULT_GLM_FAST_MODEL),
            thinking_model=get_env("GLM_THINKING_MODEL", DEFAULT_GLM_THINKING_MODEL),
        ),
        custom=CustomConfig(
            base_url=get_env("VISION_CUSTOM_BASE_URL"),
            api_key=get_env("VISION_CUSTOM_API_KEY"),
            model=get_env("VISION_CUSTOM_MODEL"),
        ),
        baidu_ocr=BaiduOCRConfig(
            api_key=get_env("BAIDU_API_KEY"),
            secret_key=get_env("BAIDU_SECRET_KEY"),
        ),
        cache_dir=get_env("DS_VISION_CACHE_DIR", CACHE_DIR),
        mineru_token=get_env("MINERU_TOKEN"),
        local_model=get_env("VISION_LOCAL_MODEL"),
    )


def status_report(cfg: Optional[Config] = None) -> Dict[str, Any]:
    """通道状态报告，供 preflight / ``--status`` 使用。"""
    # 延迟导入避免循环依赖
    from .local_probe import probe_local_runtimes

    cfg = cfg or load_config()
    runtimes = probe_local_runtimes()
    return {
        "glm": bool(cfg.glm.api_key),
        "glm_thinking": bool(cfg.glm.api_key),
        "custom": bool(cfg.custom.api_key and cfg.custom.base_url and cfg.custom.model),
        "baidu_ocr": bool(cfg.baidu_ocr.api_key and cfg.baidu_ocr.secret_key),
        "mineru": bool(cfg.mineru_token),
        "local": len(runtimes) > 0,
        "local_runtimes": [r.name for r in runtimes],
        "cache_dir": cfg.cache_dir,
    }

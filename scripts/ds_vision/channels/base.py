"""通道基类与降级链编排器。

``BaseChannel`` 强制每个通道遵循 ``attempt -> (Envelope, code)`` 契约；
``Chain`` 统一执行降级链，消除原本抄写三遍的 for 循环。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Tuple

from .. import envelope
from ..cache import Cache
from ..config import Config
from ..envelope import Envelope, EXIT_GENERIC, EXIT_OK


class BaseChannel(ABC):
    """通道抽象基类。

    子类设置 ``name`` 与 ``task_type``，实现 ``attempt``。
    ``usable`` 在构建降级链时用于过滤不可用通道（可覆盖）。
    """

    name: str = "base"
    task_type: str = "image_reasoning"

    @abstractmethod
    def attempt(
        self,
        path: str,
        *,
        prompt: str,
        cfg: Config,
        cache: Cache,
        no_cache: bool = False,
        **kwargs: Any,
    ) -> Tuple[Envelope, int]:
        ...

    def usable(self, cfg: Config) -> bool:
        """通道是否已配置 / 可达。构建降级链时过滤。"""
        return True


class Chain:
    """降级链编排器：按顺序尝试通道，遇成功即返回，全失败返回失败 Envelope。

    同一通道遇 401 / 403 / 429、网络错误或空结果时直接切换下一通道，
    不反复重试。``attempts`` 记录每次尝试，写入成功或失败 Envelope 的 metadata。
    """

    def __init__(self, channels: List[BaseChannel], task_type: str = "image_reasoning"):
        self.channels = channels
        self.task_type = task_type

    def run(self, path: str, **kwargs: Any) -> Tuple[Envelope, int]:
        attempts: List[dict] = []
        for ch in self.channels:
            env, code = ch.attempt(path, **kwargs)
            attempts.append({"name": ch.name, "code": code})
            if code == EXIT_OK and env.result and env.result.strip():
                env.metadata["attempts"] = attempts
                return env, code

        last = attempts[-1]["name"] if attempts else "none"
        return (
            envelope.fail(
                self.task_type,
                result=f"全部失败 (最后: {last})",
                tool_source=last,
                attempts=attempts,
                code=EXIT_GENERIC,
            ),
            EXIT_GENERIC,
        )

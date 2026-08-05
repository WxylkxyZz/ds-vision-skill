"""ds-vision-py：为纯文本推理模型补充视觉能力的跨平台 Python 实现。

架构继承自 ds-vision-skill：统一入口 router -> 按任务类型路由 ->
(channel 降级链) -> 标准 Envelope -> 主模型读取 result 继续推理。
"""

__version__ = "0.1.0"
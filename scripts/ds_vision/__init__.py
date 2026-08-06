"""ds-vision-skill：为纯文本推理模型补充视觉能力的跨平台 Python 实现。

架构：统一入口 router -> 按任务类型路由 -> BaseChannel 降级链 (Chain) ->
标准 Envelope -> 主模型读取 result 继续推理。

通道：视觉理解 (glm/glm-thinking/custom)、OCR (baidu-ocr，失败回退 GLM)、
文档解析 (MinerU)。本地 OCR (Tesseract) 与本地视觉模型 (local) 均已移除。
"""

__version__ = "0.2.0"

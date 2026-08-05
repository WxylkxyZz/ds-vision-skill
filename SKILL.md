---
name: ds-vision
description: >
  为纯文本推理模型补充视觉能力。当用户提供图片、截图、照片、图表、架构图、UI/代码截图、
  数学题图片、扫描件、PDF、论文、报告或文档，并要求描述、理解、推理、阅读、OCR、提取文字、
  解析图表或分析内容时使用。自动路由：图片理解走 GLM(智谱)/自定义中转/本地 Ollama，文档解析
  走 MinerU，纯文字识别走百度 OCR 或本地 Tesseract。所有工具输出标准 JSON，交主模型推理总结。
---

# DS Vision Skill

把视觉输入转换成文本或结构化 JSON。它不替代主模型，只负责识别任务、选择工具、执行视觉 / OCR / 文档解析，并把结果交给主模型继续推理。

## 使用入口

在 skill 根目录执行（需系统已装 Python 3.9+ 和 `requests`）：

```bash
# 自动路由（按文件类型 + prompt 判断）
python scripts/run.py <文件路径> --prompt "请分析" --json

# 指定 OCR 意图
python scripts/run.py <图片> --intent ocr --json

# 指定复杂视觉推理（图表/数学/UI/代码截图）
python scripts/run.py <图片> --intent reason --complex --prompt "分析趋势" --json

# 指定文档解析
python scripts/run.py <PDF> --intent document --json
```

各通道需要对应 API 密钥，通过环境变量或在项目 `.env` 中配置（见 references/channels.md）。

## 路由规则

1. **PDF / 论文 / 报告 / 长文档 / 多页扫描**：`document` → MinerU（flash → extract），解析为 Markdown。
2. **图片且需理解/推理**：`reason` → VLM，调用 `glm`（简单）或 `glm-thinking`（图表/数学/复杂 UI/代码截图）。
3. **图片且只要文字**：`ocr` → 百度 OCR，失败回退本地 Tesseract。
4. **无法判断时**：`auto` 按扩展名 + prompt 关键词自动判断。

## 降级链

- 视觉理解：`glm → glm-thinking → custom → local`
- 文档解析：`mineru flash → mineru extract`
- OCR：`baidu-ocr → tesseract-ocr → vision reasoning`

同一通道遇到 401 / 403 / 429、网络错误或空结果时**不要反复重试**，直接切换下一通道。

## 输出格式

`--json` 模式下输出统一结构：

```json
{
  "task_type": "image_reasoning | document_parsing | ocr",
  "tool_used": "实际使用的通道或模型",
  "confidence": "high | medium | low",
  "result": "识别、解析或理解后的内容",
  "metadata": {}
}
```

主模型继续推理时**优先使用 `result` 字段**。向用户报告时可简要说明 `tool_used` 和必要的降级过程。

## 缓存

- VLM 按（图片 SHA256 + prompt + 通道 + 模型）组合指纹缓存，减少重复调用成本。
- 百度 OCR 缓存 access token。
- 缓存位置：`~/.ds-vision-py/cache`。用 `--no-cache` 强制重新调用。

## 隐私

云端通道会把图片/文档发送给对应服务商。用户明确关注隐私、合同、证件、医疗、财务等敏感内容时，优先使用本地 Tesseract OCR、本地模型，或先征求确认。

## 维护约定

- Python 源码保持可读，中文通过参数传入。
- 新增通道时优先接入 `ds_vision/router.py`，再补充 `references/channels.md`。
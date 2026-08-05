<div align="center">

# 👁️ ds-vision-skill

**为纯文本推理模型补充视觉能力的标准 Agent Skill**

无缝兼容 **Claude Code · OpenAI Codex · WorkBuddy**，让任何不支持图像输入的大语言模型获得读图、OCR、文档解析能力。

![License](https://img.shields.io/badge/License-MIT-green)
![Python](https://img.shields.io/badge/Python-3.9+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Skills](https://img.shields.io/badge/Skill-Anthropic%20Agent%20Skills-purple)

</div>

---

## 📖 目录

- [为什么需要它](#-为什么需要它)
- [核心特性](#-核心特性)
- [工作原理](#-工作原理)
- [快速开始](#-快速开始)
- [安装导入](#-安装导入)
- [配置](#-配置)
- [使用](#-使用)
- [输出格式](#-输出格式)
- [降级链](#-降级链)
- [缓存策略](#-缓存策略)
- [项目结构](#-项目结构)
- [常见问题](#-常见问题)
- [隐私与安全](#-隐私与安全)
- [License](#-license)

---

## 🎯 为什么需要它

纯文本推理模型（如 DeepSeek、部分本地模型）不支持图像输入，遇到图片、截图、PDF、图表时无法直接处理。

**ds-vision-skill 是一个"视觉网关"**：它不自带视觉模型，而是把视觉输入统一转成文本或结构化 JSON，再交回主模型继续推理。它不替代主模型——只负责 *看懂*，推理与总结仍由主模型完成。

## ✨ 核心特性

- **单一入口，自动路由**：按文件类型 + 提示词自动判断任务（视觉理解 / OCR / 文档解析），无需手动指定。
- **多通道降级链**：任一通道失败自动切换下一通道，最大化可用性。
- **统一输出契约**：所有通道输出标准 JSON Envelope，主模型只需读取 `result` 字段。
- **跨平台**：Windows / macOS / Linux 全支持。
- **零依赖运行**：仅需 `Python 3.9+` 和 `requests`，无需 pip 安装。
- **成本优化**：请求指纹缓存，避免重复调用付费 API。

## 🧠 工作原理

```
┌─────────────────────────────────────────────────────────────┐
│  用户提供 图片 / 截图 / PDF / 扫描件                         │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   router（统一入口）   │
              │  自动判断任务类型      │
              └───────────────────────┘
              │          │          │
     ┌────────▼──┐  ┌────▼─────┐ ┌──▼──────────┐
     │ 文档/PDF  │  │ 纯文字    │ │ 视觉理解     │
     │           │  │ 识别      │ │ 推理         │
     └───────────┘  └──────────┘ └─────────────┘
              │          │          │
     MinerU  │  Baidu OCR│  GLM     │
     (flash→ │  →Tesseract│  →GLM-   │
      extract)│            │  thinking│
              │          │  →custom  │
              │          │  →local   │
              └────┬──────┴──────────┘
                   ▼
        ┌────────────────────┐
        │  标准 JSON Envelope │
        └────────────────────┘
                   │
                   ▼
        ┌────────────────────┐
        │ 主模型读取 result   │
        │ 字段，继续推理总结   │
        └────────────────────┘
```

## 🚀 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/WxylkxyZz/ds-vision-skill.git
cd ds-vision-skill

# 2. 配置密钥（见下方「配置」）
cp .env.example .env   # 编辑填入你的密钥

# 3. 运行（自动路由）
python scripts/run.py <文件路径> --prompt "分析这个文件" --json
```

## 📦 安装导入

### 方式一：作为 Git 依赖（推荐）

**Claude Code**
```bash
mkdir -p ~/.claude/skills
git clone https://github.com/WxylkxyZz/ds-vision-skill.git ~/.claude/skills/ds-vision
```

**OpenAI Codex**
```bash
mkdir -p ~/.codex/skills
git clone https://github.com/WxylkxyZz/ds-vision-skill.git ~/.codex/skills/ds-vision
```

### 方式二：手动复制

将本目录复制到对应 Agent 的 skills 目录下即可（SKILL.md 的 frontmatter 会被自动识别）。

## ⚙️ 配置

复制 `.env.example` 为 `.env` 并填入密钥（也可用系统环境变量，优先级更高）：

| 通道 | 用途 | 环境变量 | 是否必填 |
|---|---|---|---|
| `glm` | 简单图片理解 | `GLM_API_KEY` | 建议 |
| `glm-thinking` | 复杂视觉推理 | `GLM_API_KEY` | 建议 |
| `custom` | OpenAI 兼容中转 | `VISION_CUSTOM_BASE_URL` + `VISION_CUSTOM_API_KEY` + `VISION_CUSTOM_MODEL` | 可选 |
| `baidu-ocr` | 云端 OCR | `BAIDU_API_KEY` + `BAIDU_SECRET_KEY` | 可选 |
| `mineru` | PDF/文档解析 | `MINERU_TOKEN` | 可选 |
| `tesseract` | 本地离线 OCR | 系统安装 tesseract + `pip install pytesseract Pillow` | 可选 |

> **模型可覆盖**：`GLM_FAST_MODEL`（默认 `glm-4v-flash`）、`GLM_THINKING_MODEL`（默认 `glm-4.1v-thinking-flash`）、`VISION_LOCAL_MODEL`（默认 `qwen2.5-vl:3b`）。

## 🛠️ 使用

```bash
# 自动路由（按文件类型 + 提示词判断任务）
python scripts/run.py <文件> --prompt "分析" --json

# 指定 OCR（票据/扫描件/低清晰文字）
python scripts/run.py <图片> --intent ocr --json

# 指定复杂视觉推理（图表/数学/UI/代码截图）
python scripts/run.py <图片> --intent reason --complex --prompt "分析趋势" --json

# 指定文档解析（PDF/论文/报告）
python scripts/run.py <PDF> --intent document --json
```

### 参数说明

| 参数 | 可选值 | 说明 |
|---|---|---|
| `--intent` | `auto`(默认) / `reason` / `ocr` / `document` | 任务类型 |
| `--complex` | - | 复杂视觉推理（图表/数学/复杂 UI） |
| `--accurate-ocr` | - | 百度高精度 OCR |
| `--json` | - | 输出标准 JSON Envelope |
| `--no-cache` | - | 强制重新调用 API |
| `--prompt` | 文本 | 分析提示词 |

## 📤 输出格式

所有通道在 `--json` 模式下输出统一结构：

```json
{
  "task_type": "image_reasoning | document_parsing | ocr",
  "tool_used": "glm:glm-4v-flash",
  "confidence": "high | medium | low",
  "result": "识别、解析或理解后的内容",
  "metadata": {
    "channel": "glm",
    "model": "glm-4v-flash",
    "latency_ms": 3200,
    "cached": false,
    "attempts": []
  }
}
```

主模型继续推理时**优先使用 `result` 字段**。

## 🔁 降级链

系统按以下优先级自动降级，遇到 401/403/429、网络错误或空结果时**不反复重试**，直接切换下一通道：

| 任务 | 降级链 |
|---|---|
| 视觉理解 | `glm → glm-thinking → custom → local` |
| 复杂视觉推理 | `glm-thinking → custom → local` |
| 文档解析 | `mineru flash → mineru extract` |
| OCR | `baidu-ocr → tesseract-ocr → vision reasoning` |

## 💾 缓存策略

- **VLM**：按（图片 SHA256 + 提示词 + 通道 + 模型）组合指纹缓存，减少重复调用成本。
- **百度 OCR**：缓存 access token，避免重复认证。
- **位置**：`~/.ds-vision-py/cache`。使用 `--no-cache` 可强制重新调用。

## 📁 项目结构

```
ds-vision-skill/
├── SKILL.md                  # Skill 定义（触发条件 + 工作流 + 降级链）
├── README.md
├── LICENSE
├── .env.example              # 配置模板
├── .gitignore
├── references/
│   └── channels.md           # 通道配置表（模型/端点/环境变量）
└── scripts/
    ├── run.py                # 独立入口
    └── ds_vision/            # 核心引擎（Python 包）
        ├── router.py         # 统一路由 + 降级链（核心）
        ├── envelope.py       # 统一输出契约
        ├── config.py         # 环境变量 + .env 配置
        ├── cache.py          # 请求指纹缓存
        ├── utils.py          # 意图判断、base64、端口探测
        └── channels/
            ├── vlm.py        # glm / glm-thinking / custom / local
            ├── ocr.py        # 百度 OCR + Tesseract
            └── document.py   # MinerU 文档解析
```

## ❓ 常见问题

**Q：不配置任何密钥能运行吗？**
可以运行，但所有通道都会按降级链尝试后失败。建议至少配置 `GLM_API_KEY`。

**Q：本地 OCR 需要什么？**
系统安装 [Tesseract](https://github.com/tesseract-ocr/tesseract)，并 `pip install pytesseract Pillow`。中文识别需下载 `chi_sim` 语言包。

**Q：如何处理超大图片？**
超过 15MB 的图片会被拒绝。建议先降采样，或使用文档通道（MinerU）处理扫描件。

**Q：支持哪些图片格式？**
PNG / JPG / JPEG / WEBP / GIF / BMP / TIFF。

## 🔒 隐私与安全

云端通道会把图片/文档发送给对应服务商（智谱、百度、MinerU）。处理**合同、证件、医疗、财务**等敏感内容时，建议：

1. 优先使用本地 Tesseract OCR 或本地模型（Ollama/LM Studio）。
2. 或在发送前取得用户明确确认。

**本仓库的 `.env` 已被 `.gitignore` 排除**，提交代码时请勿包含真实密钥。

## 📄 License

[MIT](LICENSE) © 2026 [WxylkxyZz](https://github.com/WxylkxyZz)
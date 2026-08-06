<div align="center">

# 👁️ ds-vision-skill

**为纯文本推理模型补充视觉能力的 Agent Skill**

让任何不支持图像输入的大语言模型，获得读图、OCR、文档解析能力。<br/>
无缝兼容 **Claude Code · OpenAI Codex · WorkBuddy**。

![License](https://img.shields.io/badge/License-MIT-green)
![Python](https://img.shields.io/badge/Python-3.9+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Skills](https://img.shields.io/badge/Skill-Anthropic%20Agent%20Skills-purple)

</div>

---

## 🎯 为什么需要它

纯文本推理模型（DeepSeek、部分本地模型）不支持图像输入，遇到图片、PDF、图表时束手无策。

**ds-vision-skill 是一个"视觉网关"**：它不自带视觉模型，而是把视觉输入统一转成文本或结构化 JSON，再交回主模型继续推理。它不替代主模型——只负责 *看懂*，推理与总结仍由主模型完成。

## ✨ 核心特性

| 特性 | 说明 |
|---|---|
| **单一入口** | 按文件类型 + 提示词自动判断任务，无需手动指定通道 |
| **自动降级** | 任一通道失败自动切换下一通道，最大化可用性 |
| **统一契约** | 所有通道输出标准 JSON Envelope，主模型只读 `result` 字段 |
| **跨平台** | Windows / macOS / Linux 全支持 |
| **零依赖** | 仅需 `Python 3.9+` 和 `requests`，无需 pip 安装 |
| **成本优化** | 请求指纹缓存，避免重复调用付费 API |
| **一键预检** | `--status` 查看各通道配置可用性 |

## 🧠 工作原理

```
┌──────────────────────────────────────┐
│  用户提供 图片 / 截图 / PDF / 扫描件 │
└──────────────────────────────────────┘
                   │
                   ▼
         ┌──────────────────┐
         │  router 自动路由  │
         └──────────────────┘
          │        │        │
   ┌──────▼──┐ ┌───▼───┐ ┌──▼────────┐
   │ 文档/PDF│ │  OCR  │ │ 视觉推理   │
   └─────────┘ └───────┘ └───────────┘
        │          │          │
     MinerU     百度 OCR    GLM 视觉
   vlm→pipeline  ↓兜底    →thinking
        │       GLM推理   →custom
        └────────┬────────┘
                 ▼
        ┌────────────────────┐
        │  标准 JSON Envelope │
        └────────────────────┘
                 │
                 ▼
        ┌────────────────────┐
        │ 主模型读取 result   │
        │ 继续推理与总结      │
        └────────────────────┘
```

## 🚀 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/WxylkxyZz/ds-vision-skill.git
cd ds-vision-skill

# 2. 配置密钥
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

将本目录复制到对应 Agent 的 skills 目录下即可（`SKILL.md` 的 frontmatter 会被自动识别）。

## ⚙️ 配置

复制 `.env.example` 为 `.env` 并填入密钥（也可用系统环境变量，优先级更高）：

| 通道 | 用途 | 环境变量 |
|---|---|---|
| `glm` | 图像理解 | `GLM_API_KEY` |
| `glm-thinking` | 复杂视觉推理 | `GLM_API_KEY` |
| `custom` | OpenAI 兼容中转 | `VISION_CUSTOM_BASE_URL` + `VISION_CUSTOM_API_KEY` + `VISION_CUSTOM_MODEL` |
| `baidu-ocr` | 云端 OCR | `BAIDU_API_KEY` + `BAIDU_SECRET_KEY` |
| `mineru` | PDF/文档解析 | `MINERU_TOKEN` |

> **模型可覆盖**：`GLM_FAST_MODEL`（默认 `GLM-4V-Flash`）、`GLM_THINKING_MODEL`（默认 `glm-4.1v-thinking-flash`）。

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

# 查看通道配置与可用性
python scripts/run.py --status
```

### 参数说明

| 参数 | 可选值 | 说明 |
|---|---|---|
| `path` | 文件路径 | 输入文件（图片/PDF/文档） |
| `--prompt` | 文本 | 分析提示词（支持 `--prompt=值`） |
| `--intent` | `auto` / `reason` / `ocr` / `document` | 任务类型（默认 `auto`） |
| `--complex` | — | 复杂视觉推理（图表/数学/UI），首选 thinking 模型 |
| `--accurate-ocr` | — | 百度高精度 OCR |
| `--json` | — | 输出标准 JSON Envelope |
| `--no-cache` | — | 强制重新调用 API |
| `--status` | — | 打印通道状态报告后退出 |

## 📤 输出格式

所有通道在 `--json` 模式下输出统一结构：

```json
{
  "task_type": "image_reasoning | document_parsing | ocr",
  "tool_used": "glm:GLM-4V-Flash",
  "confidence": "high | medium | low",
  "result": "识别、解析或理解后的内容",
  "metadata": {
    "channel": "glm",
    "model": "GLM-4V-Flash",
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
| 视觉理解 | `glm → glm-thinking → custom` |
| 复杂视觉推理 | `glm-thinking → custom` |
| 文档解析 | `mineru vlm(推荐) → mineru pipeline(默认回退)`；`.html` 强制 `MinerU-HTML` |
| OCR | `baidu-ocr → GLM 视觉推理` |

> 文档解析的 `model_version` 三取值（`pipeline`/`vlm`/`MinerU-HTML`）经 [官方文档](https://mineru.net/apiManage/docs) 核实。

## 💾 缓存策略

- **VLM**：按（图片 SHA256 + 提示词 + 通道 + 模型）组合指纹缓存。
- **文档**：按（内容 SHA256 + mode）指纹缓存。
- **百度 OCR**：缓存 access token，避免重复认证。
- **位置**：`~/.ds-vision-py/cache`（可用 `DS_VISION_CACHE_DIR` 覆盖）。`--no-cache` 强制重新调用。

## 📁 项目结构

```
ds-vision-skill/
├── SKILL.md                  # Skill 定义（触发条件 + 工作流 + 降级链）
├── README.md
├── .env.example              # 配置模板
├── references/
│   └── channels.md           # 通道配置表
└── scripts/
    ├── run.py                # 入口（argparse）
    ├── ds_vision/            # 核心引擎
    │   ├── router.py         # 统一路由 + 降级链编排
    │   ├── envelope.py       # 统一输出契约（退出码 / error_type）
    │   ├── config.py         # Config 聚合 + 环境变量
    │   ├── cache.py          # 请求指纹缓存
    │   ├── utils.py          # 意图判断 / base64 / 文件类型
    │   └── channels/
    │       ├── base.py       # BaseChannel + Chain 降级链编排器
    │       ├── vlm.py        # glm / glm-thinking / custom
    │       ├── ocr.py        # 百度 OCR
    │       └── document.py   # MinerU 文档解析
    └── tests/                # 单元 + 降级链 mock 测试
```

## ❓ 常见问题

**Q：不配置任何密钥能运行吗？**
可以运行，但所有通道会按降级链尝试后失败。建议至少配置 `GLM_API_KEY`。

**Q：还支持本地 Tesseract OCR 吗？**
不再支持。本地 OCR 已移除，OCR 统一走百度云，失败时由 GLM 视觉推理兜底。

**Q：如何处理超大图片？**
超过 15MB 的图片会被拒绝。建议先降采样，或使用文档通道（MinerU）处理扫描件。

**Q：支持哪些图片格式？**
PNG / JPG / JPEG / WEBP / GIF / BMP / TIFF。

## 🔒 隐私与安全

云端通道会把图片/文档发送给对应服务商（智谱、百度、MinerU）。处理**合同、证件、医疗、财务**等敏感内容时，建议在发送前取得用户明确确认。

> 本仓库的 `.env` 已被 `.gitignore` 排除，提交代码时请勿包含真实密钥。

## 📄 License

[MIT](LICENSE) © 2026 [WxylkxyZz](https://github.com/WxylkxyZz)

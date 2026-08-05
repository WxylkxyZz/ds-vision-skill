# 通道配置表

记录 ds-vision-skill 支持的视觉、OCR、文档解析和本地通道。更新模型 ID、注册入口或环境变量时，优先改这里。

## 云端视觉通道

| 通道 | 类别 | 默认模型 | 环境变量 | 备注 |
|---|---|---|---|---|
| `glm` | 简单视觉理解 | `glm-4v-flash`（默认） | `GLM_API_KEY` | 快路径 |
| `glm-thinking` | 复杂视觉推理 | `glm-4.1v-thinking-flash`（默认） | `GLM_API_KEY` | 图表、数学、复杂 UI |
| `custom` | OpenAI 兼容中转 | `VISION_CUSTOM_MODEL` | `VISION_CUSTOM_BASE_URL` + `VISION_CUSTOM_API_KEY` + `VISION_CUSTOM_MODEL` | 私有或第三方服务 |

> 智谱默认模型可用 `GLM_FAST_MODEL` / `GLM_THINKING_MODEL` 覆盖；Base URL 可用 `GLM_BASE_URL` 覆盖。

## OCR 通道

| 通道 | 端点/运行时 | 环境变量 | 备注 |
|---|---|---|---|
| `baidu-ocr` | 百度 `general_basic` / `accurate_basic` | `BAIDU_API_KEY` + `BAIDU_SECRET_KEY` | access token 自动缓存 |
| `tesseract` | 本地 Tesseract | 无 | 需系统安装 tesseract + `pip install pytesseract Pillow`；隐私优先 |

## 文档解析通道

| 通道 | 端点 | 环境变量 | 备注 |
|---|---|---|---|
| `mineru` | MinerU v4 `file-urls/batch` | `MINERU_TOKEN` | PDF/论文/报告优先；flash 优先，失败回退 extract |

## 本地模型通道

| 运行时 | 默认端口 | 说明 |
|---|---:|---|
| Ollama | `11434` | 推荐本地运行时 |
| LM Studio | `1234` | OpenAI 兼容服务 |
| llama.cpp | `8080` | `llama-server` 兼容服务 |

建议模型（`VISION_LOCAL_MODEL`）：
- VRAM ≥ 8GB：`qwen2.5-vl:7b`、`llama3.2-vision:11b`
- VRAM ≥ 4GB：`qwen2.5-vl:3b`、`minicpm-v`、`moondream`
- 无 GPU：`moondream`、`smolvlm`

## 配置方式

密钥通过环境变量注入，或在 skill 根目录创建 `.env`：

```bash
# .env 示例
GLM_API_KEY=
GLM_FAST_MODEL=glm-4v-flash
GLM_THINKING_MODEL=glm-4.1v-thinking-flash
BAIDU_API_KEY=
BAIDU_SECRET_KEY=
MINERU_TOKEN=
VISION_CUSTOM_BASE_URL=
VISION_CUSTOM_API_KEY=
VISION_CUSTOM_MODEL=
VISION_LOCAL_MODEL=qwen2.5-vl:3b
```

预检通道状态：

```bash
python scripts/run.py --help
```

## 路由优先级

- 图片理解：`glm → glm-thinking → custom → local`
- 复杂视觉推理：`glm-thinking → custom → local`
- 文档解析：`mineru flash → mineru extract`
- OCR：`baidu-ocr → tesseract-ocr → vision reasoning`

## 退出码

| 码 | 含义 |
|---:|---|
| `0` | 成功 |
| `1` | 本地输入或通用错误 |
| `2` | 缺 key 或认证失败 |
| `3` | 限流 |
| `4` | 网络或服务端错误 |
| `5` | 请求被拒、模型 ID 无效或参数错误 |
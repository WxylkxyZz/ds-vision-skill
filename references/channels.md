# 通道配置表

记录 ds-vision-skill 支持的视觉、OCR、文档解析通道。更新模型 ID、注册入口或环境变量时，优先改这里。

## 云端视觉通道

| 通道 | 类别 | 默认模型 | 环境变量 | 备注 |
|---|---|---|---|---|
| `glm` | 简单视觉理解 | `GLM-4V-Flash`（默认） | `GLM_API_KEY` | 图像理解快路径 |
| `glm-thinking` | 复杂视觉推理 | `glm-4.1v-thinking-flash`（默认） | `GLM_API_KEY` | 图表、数学、复杂 UI、代码截图 |
| `custom` | OpenAI 兼容中转 | `VISION_CUSTOM_MODEL` | `VISION_CUSTOM_BASE_URL` + `VISION_CUSTOM_API_KEY` + `VISION_CUSTOM_MODEL` | 私有或第三方服务 |

> 智谱默认模型可用 `GLM_FAST_MODEL` / `GLM_THINKING_MODEL` 覆盖；Base URL 可用 `GLM_BASE_URL` 覆盖。

## OCR 通道

| 通道 | 端点 | 环境变量 | 备注 |
|---|---|---|---|
| `baidu-ocr` | 百度 `general_basic` / `accurate_basic` | `BAIDU_API_KEY` + `BAIDU_SECRET_KEY` | access token 自动缓存；OCR 失败由 router 退回 GLM 视觉推理 |

## 文档解析通道

| 通道 | 端点 | 环境变量 | 备注 |
|---|---|---|---|
| `mineru` | MinerU v4 `file-urls/batch` | `MINERU_TOKEN` | PDF/论文/报告优先；`vlm`（推荐，多模态含公式表格）优先，失败回退 `pipeline`（默认管线）；`.html` 文件强制走 `MinerU-HTML` 管线；`.md`/`.txt` 本地直接读取不触云 |

> `model_version` 三个合法取值（经 [官方文档](https://mineru.net/apiManage/docs) 核实）：`pipeline`（默认）/ `vlm`（推荐）/ `MinerU-HTML`（HTML 文件专用）。非 HTML 文件可选 `pipeline`/`vlm`，HTML 文件须用 `MinerU-HTML`。映射见 `scripts/ds_vision/channels/document.py` 顶部 `MODE_TO_MODEL_VERSION`。

## 配置方式

密钥通过环境变量注入，或在 skill 根目录创建 `.env`：

```bash
# .env 示例
GLM_API_KEY=
GLM_FAST_MODEL=GLM-4V-Flash
GLM_THINKING_MODEL=glm-4.1v-thinking-flash
BAIDU_API_KEY=
BAIDU_SECRET_KEY=
MINERU_TOKEN=
VISION_CUSTOM_BASE_URL=
VISION_CUSTOM_API_KEY=
VISION_CUSTOM_MODEL=
# DS_VISION_CACHE_DIR=~/.ds-vision-py/cache
```

预检通道状态：

```bash
python scripts/run.py --status
```

## 路由优先级

- 图片理解：`glm → glm-thinking → custom`
- 复杂视觉推理：`glm-thinking → custom`
- 文档解析：`mineru-vlm → mineru-pipeline`（`.html` 强制 `MinerU-HTML`）
- OCR：`baidu-ocr → GLM 视觉推理`

## 退出码

| 码 | 含义 |
|---:|---|
| `0` | 成功 |
| `1` | 本地输入或通用错误 |
| `2` | 缺 key 或认证失败 |
| `3` | 限流 |
| `4` | 网络或服务端错误 |
| `5` | 请求被拒、模型 ID 无效或参数错误 |

# AI 自动解说 — VLM / TTS 服务商配置情报

> 核实时间：**2026-10-02**（Asia/Shanghai）。所有 `base_url` 与 `model id` 均经**实际网络探测**验证（返回 401 = 端点存活），verifier 位于中国大陆网络。
> 标注 `未核实` 的条目表示未找到官方一手来源，**不要直接写进生产配置**。
> 探测环境实测：`api.openai.com` 解析失败（被 hosts 屏蔽），其余国内厂商与 OpenRouter 均可直连。

---

## 1. OpenAI 兼容的云端 VLM 服务

### 1.1 汇总表（可直接写入配置）

| 服务商 | OpenAI 兼容 base_url（完整） | 可用视觉 model id | 视频文件输入 | API Key 地址 | 免费额度 |
|---|---|---|---|---|---|
| **阿里云百炼**（通义千问） | `https://dashscope.aliyuncs.com/compatible-mode/v1` （旧共享域名，**仍可用**，本次实测 401 存活）<br>推荐生产：`https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` | `qwen3-vl-plus`、`qwen3-vl-flash`、`qwen3-vl-max`<br>新旗舰全模态：`qwen3.8-max`、`qwen3.8-flash`、`qwen3.8-omni-flash`<br>开源系：`qwen3-vl-235b-a22b-instruct` / `-thinking`<br>旧版：`qwen-vl-max`、`qwen-vl-plus` | ✅ 三种：<br>① `type:"video_url"` 真视频文件<br>② `type:"video"` + 图片 URL 数组<br>③ `fps` 控抽帧 | [控制台](https://modelstudio.console.alibabacloud.com/cn-beijing/settings/api-key) | 新用户每模型 **100 万 tokens**（[阿里云开发者社区](https://developer.aliyun.com/article/1759771)） |
| **智谱 AI**（GLM） | `https://open.bigmodel.cn/api/paas/v4` （实测 401 存活） | `glm-5.3-flash`、`glm-5.3-flashx`（原生多模态，支持 video）、`glm-5.3`、`glm-ocr`<br>**注意**：`glm-4v` / `glm-4.5v` 在 2026-10 官方导航中**已不在售**，勿再使用 | ✅ `glm-5.3-flashx` / `glm-5.3-flash`（OpenRouter 元数据 `input_modalities` 含 `video`） | [bigmodel.cn 控制台](https://bigmodel.cn/usercenter/proj-mgmt/apikeys) | 有免费模型（社区称 `glm-4.7-flash` 免费，`未核实`官方条款） |
| **硅基流动** SiliconFlow | `https://api.siliconflow.cn/v1` （实测 401 存活，错误体 `code:30014`） | `Qwen/Qwen3-VL-8B-Instruct`、`Qwen/Qwen3-VL-30B-A3B-Instruct`、`Qwen/Qwen2.5-VL-7B-Instruct`<br>命名规则 = `厂商/仓库名`（**未核实**完整在售清单，需登录[模型广场](https://cloud.siliconflow.cn/models)核对） | `未核实`（多数开源 VLM 走图片列表） | [cloud.siliconflow.cn/account/ak](https://cloud.siliconflow.cn/account/ak) | 新用户赠额度 + 部分小模型免费（具体数额 `未核实`） |
| **月之暗面 Kimi** | `https://api.moonshot.cn/v1` （实测 401 存活） | `kimi-k3`、`kimi-k2.6`、`kimi-k2.7-code`、`kimi-k2.7-code-highspeed`（**仅这四个支持视觉**） | ✅ 需先 `client.files.create(purpose="video")`，再以 `video_url.url = "ms://<file-id>"` 引用 | [platform.kimi.com](https://platform.kimi.com/docs/guide/use-kimi-vision-model) | `未核实` |
| **火山方舟**（豆包 Doubao） | `https://ark.cn-beijing.volces.com/api/v3` （实测 401，错误体 `AuthenticationError`） | `doubao-seed-1-6-vision`（详情页存在）；精确快照 id（如 `doubao-seed-1-6-vision-250815`）**未核实**——火山官方文档为纯 JS 渲染，无法抓取 | ✅（豆包 vision 系支持视频，具体参数 `未核实`） | [火山方舟控制台](https://console.volcengine.com/ark) | 新用户每模型赠送 tokens（`未核实`具体数额） |
| **阶跃星辰 StepFun** | `https://api.stepfun.com/v1` （实测 401，标准 OpenAI 错误体） | 视觉：`step-1v-8k`（历史型号，**未核实**是否在售）<br>现役多模态：`step-3.7-flash`（文档有专章 Cookbook） | ✅（文档有[视频理解最佳实践](https://platform.stepfun.com/docs/zh/guides/developer/video-chat)专章） | [platform.stepfun.com/interface-key](https://platform.stepfun.com/interface-key) | `未核实` |
| **OpenRouter**（国外兜底） | `https://openrouter.ai/api/v1` （实测 401 存活，**国内可直连**） | 支持视频：`qwen/qwen3.8-max-0902`、`qwen/qwen3.8-omni-flash`、`z-ai/glm-5.3-flashx`、`google/gemini-3.8-flash`、`meta/muse-spark-1.3`、`xiaomi/mimo-v2.6-flash`<br>仅图片：`openai/gpt-6.1-sol`、`openai/gpt-6-luna`、`openai/gpt-6-astra`、`anthropic/claude-sonnet-5.5` | 取决于上游（见左列） | [openrouter.ai/keys](https://openrouter.ai/keys) | 有 `:free` 后缀免费型号（本次抓到的免费型号均不支持视觉） |
| **OpenAI 官方** | `https://api.openai.com/v1` | `gpt-6-astra`、`gpt-6.1-sol`、`gpt-6-luna`（`input_modalities` 含 `image` + `file`，**均不支持 video**）<br>`gpt-4o` / `gpt-5` 已非现役，勿用 | ❌ 无 `video` modality | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | 无 |

### 1.2 关键坑位

- **阿里百炼域名正在换代**：官方文档（2026-09-28 更新）明确 `dashscope.aliyuncs.com` 为 *Legacy shared domain, still available*，推荐迁到 `{WorkspaceId}.cn-beijing.maas.aliyuncs.com`。用户笔记里的 `dashscope.aliyuncs.com/compatible-mode/v1` **依然正确可用**，可放心先用，后续再换。来源：[Base URL overview](https://www.alibabacloud.com/help/en/model-studio/base-url)。
- **百炼的 base_url 是"业务空间专属"时，API Key 必须同空间**，否则 401。
- **百炼视频输入三种写法**（来源：[图像与视频理解](https://www.alibabacloud.com/help/zh/model-studio/vision)）：
  - 真视频文件：`{"type":"video_url","video_url":{"url":"https://.../1.mp4"},"fps":2}`
  - 图片列表当视频：`{"type":"video","video":["url1.jpg","url2.jpg"],"fps":2}`
  - `fps` 范围 `[0.1, 10]`，默认 `2.0`；`max_frames` **仅 DashScope SDK 可用**，OpenAI 兼容模式不可用。
- **百炼思考模式**：`qwen3-vl-plus` / `qwen3-vl-flash` 默认 `enable_thinking=false`（适合实时解说，**保持默认即可**）；`qwen3.8` / `qwen3.7` / `qwen3.6` / `qwen3.5` 系列默认 `true`（实时解说必须显式关掉，否则首字延迟暴涨）。非标准参数经 `extra_body` 传：[详细](https://www.alibabacloud.com/help/zh/model-studio/vision)。
- **Kimi 视觉不支持 URL 图片**——只接受 base64 data URL 或 `ms://<file-id>`。这直接影响抓帧上传链路：**必须本地编码 base64**。且请求体上限 **100 MB**。来源：[配置 Kimi 视觉模型](https://platform.kimi.com/docs/guide/use-kimi-vision-model)。
- **Kimi 的 `content` 必须是 JSON 数组**，不能把数组序列化成字符串，否则不保证按视觉处理（同上来源）。
- 生成包含文字的 prompt 时注意：百炼官方建议通用对话场景**不要设 `System Message`**，把角色设定放进 `User Message` 效果更好。

---

## 2. Ollama 本地视觉模型（Windows / 8GB 显存）

### 2.1 下载与国内可达性

| 项 | 值 |
|---|---|
| 最新版本 | **v0.35.0**（2026-09-28 发布，实测 GitHub API 可读） |
| 官方 Windows 安装包 | `https://ollama.com/download/OllamaSetup.exe` |
| 实测 HTTP 状态 | ✅ **200**，`Content-Length: 1571105888`（约 **1.46 GiB**），`Content-Type: application/octet-stream` |
| 国内可否直连 | ✅ **可以**。本机在中国大陆网络实测 `ollama.com/download/OllamaSetup.exe` 直接返回 200 完整大小，无需代理 |
| GitHub 备用（若 ollama.com 抽风） | `https://github.com/ollama/ollama/releases/latest/download/OllamaSetup.exe`（同样实测 200，同尺寸） |
| 清华 / 阿里云镜像 | ❌ **不存在**（`mirrors.aliyun.com/ollama/`、`mirrors.tuna.tsinghua.edu.cn/ollama/` 均返回 404） |

> 注意：`OllamaSetup.exe` 有 **1.46 GiB**（内含 CUDA/ROCm 运行时），下载慢是体积问题不是被墙。

### 2.2 Ollama 库里**真正支持视觉**的模型（实测 `/library/<name>/tags` 抓取）

> **重要变化**：截至 2026-10，Ollama 官方 vision 分类里 **`llava`、`gemma3`、`llama3.2-vision` 已被新模型挤到后排**，主力是 `qwen3.5/3.6/3.8`、`gemma4`、`minicpm-v4.x`。用户笔记里的 `qwen3-vl` **确实存在**。

| `ollama pull` 名称 | Q4 体积（实测） | 8GB 显存 | 中文能力 |
|---|---|---|---|
| `qwen3-vl:2b` / `:2b-instruct` / `:2b-thinking` | **1.9 GB** | ✅ 全量上卡，余量大 | 好（Qwen 系中文原生） |
| `qwen3-vl:4b` / `:4b-instruct` / `:4b-thinking` | **3.3 GB** | ✅ 全量上卡 | **很好**，中文性价比首选 |
| `qwen3-vl:8b-instruct` | **6.1 GB** | ⚠️ 勉强全量（+KV cache/视觉编码器易溢出，建议 `num_ctx` 调小） | 很好 |
| `qwen3-vl:30b-a3b-instruct` | 20 GB | ❌ 需 CPU offload，很慢 | 很好 |
| `qwen3.5:2b-q4_K_M` | 1.9 GB | ✅ | 很好（原生多模态） |
| `qwen3.5:4b-q4_K_M` | **3.4 GB** | ✅ | 很好 |
| `qwen3.5:9b-q4_K_M`（= `latest`） | **6.6 GB** | ⚠️ 紧张 | 很好 |
| `qwen3.6:27b-q4_K_M` | 17 GB | ❌ | 很好 |
| `qwen3.8:27b-q4_K_M` | 18 GB | ❌ | 很好 |
| `gemma4:e2b-it-qat` | 4.3 GB | ✅ | 中等（Gemma 中文一般） |
| `gemma4:e4b-it-qat`（= `latest`） | 6.1 GB | ⚠️ 紧张 | 中等 |
| `gemma4:12b-it-qat` | 7.2 GB | ❌ 超 8GB | 中等 |
| `minicpm-v4.5:8b` / `q4_K_M` | **6.1 GB** | ⚠️ 紧张 | 好（面壁智能，中文优化 + 高 FPS 视频） |
| `minicpm-v4.6:1b` | **1.6 GB** | ✅ 极轻 | 好（1B 端侧，手机级） |
| `qwen2.5vl:3b-q4_K_M` | 3.2 GB | ✅ | 好（旧版，已被 qwen3-vl 取代） |
| `qwen2.5vl:7b-q4_K_M` | 6.0 GB | ⚠️ | 好 |
| `llava:7b-v1.6-mistral-q4_K_M` | 5.0 GB | ✅ | **差**（英文为主，中文易崩） |
| `llama3.2-vision:11b-instruct-q4_K_M` | 7.8 GB | ❌ 超 | **差** |
| `glm-ocr:latest` | 未记录 | — | 文档 OCR 专用（GLM-V 架构） |

**未在 Ollama 库中查到**：`internvl` 系列（无官方 tag）。

### 2.3 8GB（RTX 4060 Laptop）实际推荐

- **唯一舒适档：`qwen3-vl:4b-instruct`（3.3 GB）** → 权重 + 视觉编码器 + KV cache 约 5–5.5 GB，留出 ~2.5 GB 给 Windows 桌面/浏览器。**这是本机的最优本地选择**。
- `qwen3-vl:8b-instruct`（6.1 GB）在 8GB 上会贴近上限：需要 `num_ctx` 压到 4096 以下、关闭其他占显存程序，且长视频帧序列会 OOM。
- `minicpm-v4.6:1b`（1.6 GB）适合"要极低延迟 + 只要粗略描述"的降级档。
- 速度：**未核实**（未在 4060 Laptop 上实测 tokens/s；不要照抄网上数字）。

### 2.4 Ollama API：`/api/chat` 传图片的精确格式

**结论：`images` 是「纯 base64 字符串」数组，必须去掉 `data:image/jpeg;base64,` 前缀。**
官方文档原文：*"SDKs accept file paths, URLs or raw bytes while the REST API expects base64-encoded image data."* —— 官网示例用 `base64 < test.jpg | tr -d '\n'`，即裸 base64。来源：[Ollama Vision 文档](https://docs.ollama.com/capabilities/vision)。

```jsonc
// POST http://localhost:11434/api/chat
{
  "model": "qwen3-vl:4b-instruct",
  "messages": [
    {
      "role": "user",
      "content": "这是视频最近的画面，请用一句中文解说此刻发生的事。",
      "images": ["<纯base64，无 data: 前缀，无换行>", "<第二帧base64>"]
    }
  ],
  "stream": true,          // false = 一次性返回完整 JSON
  "think": false,          // 关闭思考链，降低首字延迟
  "keep_alive": "30m",     // 关键：保持模型常驻显存，避免每帧冷加载
  "options": {
    "num_ctx": 4096,       // 8GB 显存务必压小
    "num_predict": 80,
    "temperature": 0.8
  }
}
```

Python 侧正确编码：
```python
import base64
b64 = base64.b64encode(open("frame.jpg","rb").read()).decode("ascii")  # 不要加 data:image/jpeg;base64,
```

其他端点：`POST /api/generate`（同样 `images` 数组）、`GET /api/tags`（列本地模型）、`GET /api/ps`（看显存里驻留了什么）、`GET /api/version`。`keep_alive` 设 `-1` 可永久驻留。来源：[Generate a chat message](https://docs.ollama.com/api/chat)。

---

## 3. edge-tts

### 3.1 版本与依赖

| 项 | 值 |
|---|---|
| PyPI 最新版 | **7.2.8**（[pypi.org/project/edge-tts](https://pypi.org/project/edge-tts/)） |
| 安装 | `pip install edge-tts`（pypi.org 国内可用，**无需换源**） |
| 依赖 | 仅 `aiohttp>=3.8.0,<4.0.0`、`certifi`、`tabulate`、`typing-extensions`。**不需要 Azure SDK** |
| 是否免费 | ✅ 免费，走 Microsoft Edge「大声朗读」消费级服务，无需 API Key |
| Python 要求 | `>=3.7` |

### 3.2 中文普通话音色（**实测 live 端点返回的全部 14 个**）

> 探测方式：直接请求 `speech.platform.bing.com/consumer/speech/synthesize/readaloud/voices/list`。**免费端点只有 14 个中文音色**，与 Azure 官方文档列出的 41 个中文音色**不一致**——文档里的 `zh-CN-XiaomoNeural`、`zh-CN-XiaohanNeural`、`zh-CN-YunjianNeural` 之外的大部分、以及全部 `Multilingual`/`DragonHD` 音色**在 edge-tts 免费端点会取不到**。

| 音色 ShortName | 性别 | 官方 ContentCategories | 官方 VoicePersonalities |
|---|---|---|---|
| `zh-CN-XiaoxiaoNeural` | 女 | News, Novel | Warm |
| `zh-CN-XiaoyiNeural` | 女 | Cartoon, Novel | Lively |
| **`zh-CN-YunjianNeural`** | 男 | **Sports**, Novel | **Passion** |
| `zh-CN-YunxiNeural` | 男 | Novel | Lively, Sunshine |
| `zh-CN-YunxiaNeural` | 男 | Cartoon, Novel | Cute |
| `zh-CN-YunyangNeural` | 男 | News | Professional, Reliable |
| `zh-CN-liaoning-XiaobeiNeural` | 女 | Dialect（东北官话） | Humorous |
| `zh-CN-shaanxi-XiaoniNeural` | 女 | Dialect（中原官话·陕西） | Bright |

### 3.3 广东话 / 台湾腔音色（实测）

| 音色 | 性别 | Locale | 地区 |
|---|---|---|---|
| `zh-HK-HiuMaanNeural` | 女 | zh-HK | 香港粤语 |
| `zh-HK-HiuGaaiNeural` | 女 | zh-HK | 粤语（Traditional） |
| `zh-HK-WanLungNeural` | 男 | zh-HK | 香港粤语 |
| `zh-TW-HsiaoChenNeural` | 女 | zh-TW | 台湾 |
| `zh-TW-HsiaoYuNeural` | 女 | zh-TW | 台湾国语 |
| `zh-TW-YunJheNeural` | 男 | zh-TW | 台湾 |

### 3.4 体育/游戏解说音色推荐

**首选 `zh-CN-YunjianNeural`** —— 微软官方标签就是 `ContentCategories: ["Sports", "Novel"]` + `VoicePersonalities: ["Passion"]`，是全表唯一 Sports 分类音色。
**次选 `zh-CN-YunxiNeural`**（Lively + Sunshine，年轻男声，游戏解说感强）。

> ⚠️ **关键限制**：Azure 的 SSML `style="sports_commentary_excited"` 是 **Azure 付费 TTS 专有**，**edge-tts 免费端点不支持 `style`**。`edge_tts.Communicate` 的构造签名里根本没有 `style` 参数（实测）：
> ```
> Communicate(text, voice='en-US-EmmaMultilingualNeural', *, rate='+0%', volume='+0%',
>             pitch='+0Hz', boundary='SentenceBoundary', connector=None,
>             proxy=None, connect_timeout=10, receive_timeout=60)
> ```
> **替代方案**：选天生高能量音色（Yunjian/Yunxi）+ `rate="+25%"` 提速 + 短句 + 感叹号堆叠，靠文本节奏制造激情。

### 3.5 Python 调用方式（实测通过）

**流式输出 mp3（推荐，边生成边播，适合直播）：**
```python
import asyncio, edge_tts

async def speak(text: str, out: str = "commentary.mp3"):
    communicate = edge_tts.Communicate(
        text,
        "zh-CN-YunjianNeural",
        rate="+25%",        # 体育解说提速
        pitch="+0Hz",
        volume="+0%",
        boundary="WordBoundary",   # ← 关键，见下
    )
    with open(out, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])          # 裸 mp3 字节，可直接推给前端

asyncio.run(speak("球进了！漂亮！三比二！"))
```

**极简落盘版：** `await edge_tts.Communicate(text, voice).save("out.mp3")`（另有 `save_sync` / `stream_sync` 同步封装）。

**字幕/口型同步（实测数据）：**
- `boundary="SentenceBoundary"`（**默认**）：中文按 `。！？` 切分。实测 `"球进了！漂亮！三比二！"` → 3 个事件：`球进了！`(offset 1000000)、`漂亮！`(13250000)、`三比二！`(24750000)。
- `boundary="WordBoundary"`：**中文会输出单字级时间戳**（实测同一句话 → 5 个事件：`球`/`进`/`了`/`漂亮`/`三比二`）。**做逐字高亮必须显式传 `boundary="WordBoundary"`**，否则拿不到任何 WordBoundary 事件（实测默认配置下 `WordBoundary` 计数为 0）。
- `offset` 单位 = **100 纳秒**（1000000 = 0.1 s）。

**list_voices：** `await edge_tts.list_voices()` 返回 live 全量清单，建议启动时拉一次并按 `Locale.startswith(("zh-",))` 过滤，**不要硬编码 Azure 文档里的音色名**。

### 3.6 中文数字/英文混读技巧

- **SSML 完全不可用** ❌（实测）：`<speak>`/`<break>`/`<say-as>` 标签**会被当纯文本读出来**。传 `'<say-as interpret-as="digits">3</say-as>'` 时，boundary 事件返回的文本是 `say-as interpret-as="digits">3</say-as` —— 标签被当字念了。
- 官方 README 亦确认：*"Support for custom SSML was removed because Microsoft prevents the use of any SSML that could not be generated by Microsoft Edge itself... the service only permits a single `<voice>` tag with a single `<prosody>` tag inside it."* 来源：[edge-tts PyPI](https://pypi.org/project/edge-tts/)
- **因此必须做文本归一化**（在送 TTS 之前）：
  | 场景 | 不要送 | 改送 |
  |---|---|---|
  | 比分 | `3:2` | `三比二` |
  | 时间 | `第87分钟` | `第八十七分钟` |
  | 大数 | `12000人` | `一万两千人` |
  | 英文术语 | `Mbappé` / `VAR` | `姆巴佩` / `V-A-R`（逐字母加连字符）或直接译名 |
  | 停顿 | `<break time="1s"/>` | 用中文标点：`，`（短停）、`。`（长停）、`——`（拖音） |
- **参数格式**（实测有效，Microsoft 官方 prosody 规范）：
  - `rate`：`"+25%"` / `"-50%"`；有效区间 **0.5–2 倍**（`-50%` ~ `+100%`）。常量亦可：`x-slow`/`slow`/`medium`/`fast`/`x-fast`。
  - `pitch`：`"+0Hz"` / `"-50Hz"` / `"+2st"`（半音）/ `"+20%"`。**Hz 后缀必需**，`"0"` 无效。
  - `volume`：`"+0%"` / `"-50%"`。
  - CLI 里负值要写 `--rate=-50%`（不能有空格，否则被当命令行选项）。来源：[SSML prosody 文档](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-synthesis-markup-voice)

### 3.7 2026 年现状与风险

- ✅ **仍免费、仍可用**。本次在中国大陆网络实测：成功合成 20 KB / 24 KB mp3，耗时约 **1.27 s**，**无需代理**。
- ✅ 活跃维护：版本从 7.2.1 一路发到 7.2.8。
- ⚠️ **风险**：走的是 Edge 浏览器消费级端点（非 Azure SLA），**未核实**存在官方公布的限流阈值。已知社区反馈存在偶发 403 / 连接重置。
- 🛡️ **生产建议**：
  1. 加 `try/except` 重试（指数退避，2–3 次）；
  2. 预生成常用短语（"球进了""漂亮"）缓存成 mp3，避免每句话都打网络；
  3. ✅ **本项目 `app/tts.py` 的 `FALLBACK_VOICES` 已核对无误** —— 清单里 12 个音色**全部**在实测的 14 个 live 音色白名单内，**没有** Azure 专属音色，不会出现"选中后取音频失败"。相对 live 端点仅少收录 **2 个**：`zh-HK-HiuGaaiNeural`、`zh-TW-HsiaoYuNeural`，可按需补齐。

---

## 4. 本地 transformers 视觉模型（备用）

> 全部仓库已用 `hf-mirror.com/api/models/<repo>` **逐一验证存在**（返回 200 且带 downloads 计数），`HF_ENDPOINT=https://hf-mirror.com` 可下载。

| 模型 | hf-mirror 仓库名 | 权重体积（实测 sum of siblings） | 4bit 量化后显存 | 8GB 可行性 |
|---|---|---|---|---|
| **Qwen3-VL-2B-Instruct** | `Qwen/Qwen3-VL-2B-Instruct` | 4.27 GB (BF16) | **~1.8–2.2 GB** | ✅ 很宽裕 |
| **Qwen3-VL-4B-Instruct** | `Qwen/Qwen3-VL-4B-Instruct` | 8.89 GB (BF16) | **~3.2–3.8 GB** | ✅ **甜点档** |
| **Qwen3-VL-8B-Instruct** | `Qwen/Qwen3-VL-8B-Instruct` | 17.55 GB (BF16, 4 shards) | **~6.0–7.0 GB** | ⚠️ 临界 |
| Qwen3-VL-8B 现成 4bit | `cyankiwi/Qwen3-VL-8B-Instruct-AWQ-4bit`<br>`unsloth/Qwen3-VL-8B-Instruct-unsloth-bnb-4bit` | — | ~6 GB | ⚠️ 临界（推荐用这两个省事） |
| Qwen3-VL-8B FP8 | `Qwen/Qwen3-VL-8B-Instruct-FP8` | — | ~9 GB | ❌ 需 Hopper+ |
| Qwen3-VL-30B-A3B | `Qwen/Qwen3-VL-30B-A3B-Instruct` | — | ~18 GB (MoE 3B 激活) | ❌ |
| Qwen2.5-VL-3B-Instruct | `Qwen/Qwen2.5-VL-3B-Instruct` | — | ~2.5 GB | ✅（旧版） |
| Qwen2.5-VL-7B-Instruct | `Qwen/Qwen2.5-VL-7B-Instruct` | 16.60 GB (5 shards) | ~5.5–6.5 GB | ⚠️（旧版） |
| InternVL3-8B | `OpenGVLab/InternVL3-8B-hf` | — | ~6–7 GB | ⚠️ |
| InternVL3.5-8B | `OpenGVLab/InternVL3_5-8B-HF` | — | ~6–7 GB | ⚠️ |
| MiniCPM-V-4.5 | `openbmb/MiniCPM-V-4_5` | — | ~6 GB（8B） | ⚠️ |
| MiniCPM-V-4.6 | `openbmb/MiniCPM-V-4.6` | — | ~1.5 GB（1B 级） | ✅ 极轻 |
| MiniCPM-V-4.6 4bit | `openbmb/MiniCPM-V-4.6-AWQ`、`-BNB`、`-GPTQ` | — | ~1–2 GB | ✅ |

**关于 Qwen3.5/3.6/3.8 的开源权重**：hf-mirror 上**没有** `Qwen/Qwen3.5-VL-*`、`Qwen/Qwen3.6-VL-*`、`Qwen/Qwen3.8-VL-*` 官方仓库（搜索只返回第三方量化和微调）。这些代次目前主要通过**云端 API**（百炼/OpenRouter）提供。**结论：本地部署请认准 `Qwen/Qwen3-VL-*`**。

**显存数字说明**：上表 4bit 显存为**按参数量推算的估算值**（4bit ≈ 0.55 GB/1B 参数 + 视觉编码器 + KV cache + 激活开销），**非实测**。请以本机 `torch.cuda.max_memory_allocated()` 为准。

### 4.1 中文视频解说效果排序（结论）

1. **`Qwen/Qwen3-VL-4B-Instruct`（4bit，~3.5 GB）** —— 8GB 上的最佳平衡：Qwen3-VL 系原生支持**时间戳对齐 + 视频事件定位**，中文体育术语准，速度可接受。
2. `Qwen/Qwen3-VL-8B-Instruct`（4bit）—— 效果更好但显存临界，适合只跑模型不跑别的。
3. `openbmb/MiniCPM-V-4.6`（1B，~1.5 GB）—— 高 FPS 视频理解是强项，适合极致低延迟降级档。
4. `OpenGVLab/InternVL3_5-8B-HF` —— 中文不错，但生态/量化支持不如 Qwen 系顺手。
5. `Qwen/Qwen2.5-VL-3B-Instruct` —— 旧版，仅当 Qwen3-VL 装不上时用。

---

## 5. 「8GB 显存 Windows 笔记本 + 中国大陆网络」最优组合

### 🏆 云端方案（主推）

```jsonc
{
  "vlm": {
    "provider": "openai",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "api_key": "<DASHSCOPE_API_KEY>",
    "model": "qwen3-vl-plus",
    "extra_body": { "enable_thinking": false },
    "temperature": 0.8,
    "max_tokens": 80,
    "timeout": 60
  },
  "tts": {
    "provider": "edge",
    "voice": "zh-CN-YunjianNeural",
    "rate": "+25%",
    "pitch": "+0Hz",
    "volume": "+0%"
  }
}
```

**为什么**：`qwen3-vl-plus` 原生支持 `video_url` 真视频 + `fps` 抽帧（体育赛事官方建议调高 fps），中文解说不需翻译层，默认关思考模式首字延迟低，国内直连零代理，新用户 100 万免费 tokens。配 `zh-CN-YunjianNeural`（微软官方 Sports/Passion 标签）。

**备选/降级链**：智谱 `glm-5.3-flash`（`https://open.bigmodel.cn/api/paas/v4`）→ 硅基流动 `Qwen/Qwen3-VL-8B-Instruct`（`https://api.siliconflow.cn/v1`）→ OpenRouter `qwen/qwen3.8-max-0902`（`https://openrouter.ai/api/v1`，国内实测可连，作最后兜底）。
**❌ 不要用** `api.openai.com`（本次实测 DNS 解析失败）和任何 `gpt-4o`/`gpt-5` 型号（已非现役）。

### 🏆 本地方案（离线兜底）

```jsonc
{
  "vlm": {
    "provider": "ollama",
    "base_url": "http://localhost:11434",
    "model": "qwen3-vl:4b-instruct",   // 3.3 GB，8GB 显存舒适区
    "extra_body": { "think": false, "keep_alive": "30m",
                    "options": { "num_ctx": 4096, "num_predict": 80 } }
  }
}
```
安装：`https://ollama.com/download/OllamaSetup.exe`（1.46 GiB，国内实测直连 200）→ `ollama pull qwen3-vl:4b-instruct`。
若想要 transformers 后端：`Qwen/Qwen3-VL-4B-Instruct` + `load_in_4bit=True` + `HF_ENDPOINT=https://hf-mirror.com`（约 3.5 GB）。

### ⚠️ 需要修的既有配置

`app/config.py` 第 17 行默认 `"model": "qwen-vl-max-latest"` —— 该 id 在 2026-10 百炼文档中**已不出现**（现役为 `qwen-vl-max` / `qwen3-vl-plus` / `qwen3.8-max`）。建议改为 **`qwen3-vl-plus`**。

---

## 6. 未核实清单（不要写进生产配置）

- 火山方舟 `doubao-seed-1-6-vision` 的**精确快照 model id**（官方文档为 JS 渲染，抓不到）
- 阶跃星辰 `step-1v-8k` 是否仍在售；Step 现役视觉 model id 全称
- 硅基流动完整在售多模态模型清单与准确名称
- 各厂商 2026 年**免费额度**的确切数额（除阿里"每模型 100 万 tokens"有社区来源外）
- Ollama 在 RTX 4060 Laptop 上的实测 tokens/s
- 上表 4bit 显存数字（为推算值，非实测）

---

## 附：本文所有一手来源

- [阿里云百炼 Base URL overview](https://www.alibabacloud.com/help/en/model-studio/base-url)
- [阿里云百炼 OpenAI Chat 兼容接口](https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions)
- [阿里云百炼 图像与视频理解](https://www.alibabacloud.com/help/zh/model-studio/vision)
- [阿里云百炼 OpenAI Vision 接口兼容](https://www.alibabacloud.com/help/zh/model-studio/qwen-vl-compatible-with-openai)
- [智谱 OpenAI API 兼容](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction) ｜ [GLM-5.3-Flash 多模态](https://docs.bigmodel.cn/cn/guide/models/vlm/glm-5.3-flash)
- [硅基流动快速上手](https://docs.siliconflow.cn/docs/userguide/quickstart) ｜ [多模态输入](https://docs.siliconflow.cn/docs/userguide/capabilities/multimodal-vision)
- [Kimi 配置视觉模型](https://platform.kimi.com/docs/guide/use-kimi-vision-model)
- [火山方舟兼容 OpenAI SDK](https://ark.volcengine.com/region:cn-beijing/docs/ark/compatible-with-openai-sdk?lang=zh)
- [StepFun 图片理解最佳实践](https://platform.stepfun.com/docs/zh/guides/developer/image-chat) ｜ [视频理解](https://platform.stepfun.com/docs/zh/guides/developer/video-chat)
- [OpenRouter Models API](https://openrouter.ai/api/v1/models)
- [Ollama Vision 能力文档](https://docs.ollama.com/capabilities/vision) ｜ [/api/chat](https://docs.ollama.com/api/chat) ｜ [模型库 vision 分类](https://ollama.com/search?c=vision)
- [edge-tts on PyPI](https://pypi.org/project/edge-tts/)
- [Microsoft Azure 语言与音色支持](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts)
- [Microsoft SSML 音色与韵律](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-synthesis-markup-voice)
- [hf-mirror.com](https://hf-mirror.com) ｜ [Qwen3-VL-8B-Instruct](https://hf-mirror.com/Qwen/Qwen3-VL-8B-Instruct) ｜ [Qwen3-VL-4B-Instruct](https://hf-mirror.com/Qwen/Qwen3-VL-4B-Instruct)

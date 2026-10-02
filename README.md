# AI 自动解说工作台 · ai-live-commentary

> 给任意视频源配一个 AI 解说员。**在网页里挑「视觉理解模型」+「语音合成模型」**，接上直播流 / 摄像头 / 屏幕 / 本地视频，
> 它就会像解说员一样边看边说 —— 文字实时滚动，同时用中文音色播报出来。

<sub>Pick any vision model + any TTS model in the browser, point it at a live stream, webcam, screen or video file,
and get real-time spoken commentary. Chinese-first UI. English TL;DR at the bottom.</sub>

```
直播流 ─┐
摄像头 ─┤                  ┌── 云端 API (OpenAI 兼容)
屏幕   ─┼─► ffmpeg 抓帧 ─► ┤── 本地 Ollama          ─► 一句中文解说 ─► edge-tts ─► 网页实时播放
视频   ─┘   (环形缓冲)      └── 本地 transformers
```

---

## 为什么做这个

[LiveCC](https://github.com/showlab/livecc)（CVPR'25）是首个开源实时视频解说模型，但它有几个现实门槛：
7B 全精度要 ~16GB 显存、官方推理硬依赖 `flash-attn` + `liger-kernel`（Windows 装不了）、训练语料以英文体育解说完主。

所以这个项目把「模型」做成了**可插拔后端**：视觉理解和语音合成都只是网页上的一个下拉框。
你可以用免费的本地模型，也可以用中文效果更好的云端 API，随时切换，不用改代码。

---

## 功能

| 能力 | 说明 |
| --- | --- |
| **三种视觉后端** | 云端 OpenAI 兼容 API（阿里百炼 / 智谱 / 硅基流动 / Kimi / 火山方舟 / OpenRouter / OpenAI）· 本地 Ollama · 本地 transformers（Qwen-VL / LiveCC 等） |
| **三种语音后端** | edge-tts（14 个中文音色，免费无需 Key）· OpenAI 兼容 TTS API · 关闭（只要文字） |
| **四类输入源** | 直播流 `rtmp://` `*.m3u8` `*.flv` `rtsp://` · 摄像头 · 屏幕捕获 · 本地视频文件 |
| **实时解说** | 按间隔采样多帧送模型，带历史去重避免复读机，SSE 实时推送到网页 |
| **自动配音** | 解说生成即合成语音，网页按顺序播放，可逐条重播 |
| **9 种解说风格** | 体育 / 游戏 / 纪录片 / 教学 / 带货 / 会议 / 无障碍 / 吐槽 + 自定义提示词 |
| **导出** | 解说文案 TXT、字幕 SRT |
| **零配置起步** | 视觉模型选「自检模式」可在不接任何模型的情况下验证整条链路 |

---

## 快速开始

### Windows 一键脚本

```bat
install.bat     :: 建 .venv 并装依赖
start.bat       :: 启动，浏览器打开 http://127.0.0.1:8848
```

### 手动安装（任意平台）

```bash
git clone https://github.com/chenyuwebwawa/ai-live-commentary.git
cd ai-live-commentary

python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python -m app.main
# 浏览器打开 http://127.0.0.1:8848
```

> **不需要手动装 ffmpeg**：程序会依次找 `FFMPEG_BIN` 环境变量 → 系统 PATH → `imageio-ffmpeg` 自带的二进制。
> 想要完整功能（拉流、屏幕捕获、摄像头）建议装系统版 ffmpeg，Windows 上可用 `winget install ffmpeg`。

### 第一次用

1. 左侧「**视觉模型**」：默认是 `自检模式`（不调用模型，只验证链路通不通）。
2. 左侧「**视频源**」：选一种输入。
3. 右上角点 **▶ 开始解说**。

确认链路没问题后，再按下面配一个真正的视觉模型。

---

## 一、配视觉理解模型

### 方案 A：本地 Ollama（免 Key，8GB 显存推荐）

```bash
# 1. 装 Ollama：https://ollama.com/download
# 2. 拉一个视觉模型
ollama pull qwen3-vl:4b-instruct   # 3.3GB，8GB 显存舒适区，中文好 —— 首选
ollama pull qwen3-vl:2b            # 1.9GB，要极低延迟时的降级档
ollama pull qwen3-vl:8b-instruct   # 6.1GB，理解更好，但 8GB 上很紧
```

网页里「视觉模型」选 **本地 Ollama**，点「检测本机 Ollama 模型」自动列出已装模型。

> ⚠️ **上下文必须够大**：Ollama 按显存自动给的 4096 装不下 4 帧 448p 画面（实测要 4454 tokens，会直接报
> `exceed_context_size_error`）。程序默认已设成 **8192**；显存吃紧就在「额外参数」里填 `{"num_ctx": 6144}`，
> 或者把「每次送几帧」降到 3、高度降到 336。
>
> `llava`、`llama3.2-vision` 中文能力差，不建议；`qwen2.5vl` 已被 `qwen3-vl` 取代。

### 方案 B：云端 OpenAI 兼容 API（中文效果更好，不吃显存）

| 服务商 | Base URL | 模型 ID 示例 | 备注 |
| --- | --- | --- | --- |
| 阿里云百炼（通义千问 VL） | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3-vl-plus`、`qwen3-vl-flash` | 中文视频理解第一梯队，新用户有免费额度 |
| 智谱 AI（GLM） | `https://open.bigmodel.cn/api/paas/v4` | `glm-5.3-flash` | 便宜，适合长时间挂着 |
| 硅基流动 SiliconFlow | `https://api.siliconflow.cn/v1` | `Qwen/Qwen3-VL-8B-Instruct` | 一个 Key 调多家开源模型 |
| 月之暗面 Kimi | `https://api.moonshot.cn/v1` | `kimi-k3` 等（部分带视觉） | 视觉接口只收 base64，本程序已按 base64 发送 |
| 火山方舟（豆包） | `https://ark.cn-beijing.volces.com/api/v3` | 控制台的推理接入点 ID（`ep-` 开头） | 必须填接入点 |
| OpenRouter | `https://openrouter.ai/api/v1` | `qwen/qwen3.8-max-0902` 等 | 兜底用 |
| OpenAI | `https://api.openai.com/v1` | 当前旗舰视觉型号 | 需要代理 |

> 模型 ID 迭代很快，**以各家控制台为准**。拿不准就先点「测试连接」，它会返回真实报错。
> 各家的坑位、免费额度、视频输入方式整理在 [`docs/provider-research.md`](docs/provider-research.md)。
>
> **额外参数（JSON）** 可透传各家私有字段，例如关掉思考模式降低首字延迟：`{"enable_thinking": false}`。

### 方案 C：本地 transformers（Qwen3-VL / LiveCC）

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
pip install transformers accelerate qwen-vl-utils bitsandbytes pillow-heif
```

网页里选 **本地 transformers**，填模型路径或 HuggingFace 仓库名：

- `Qwen/Qwen3-VL-4B-Instruct` —— 8GB 显存 + 4bit 最稳
- `chenjoya/LiveCC-7B-Instruct` —— LiveCC 官方权重（英文体育解说）

> 8GB 显存**必须勾选 4bit 量化**，否则 7B 全精度要 ~16GB。
> 国内网络可设 `HF_ENDPOINT=https://hf-mirror.com`（程序默认已设）。

---

## 二、配语音合成

默认 **edge-tts**：微软的在线语音服务，免费、不需要 Key、不占显存。

- 默认音色 `zh-CN-YunjianNeural`（浑厚有力，微软唯一 Sports 标签音色）+ 语速 `+20%`
- 可选 14 个中文音色：`zh-CN-*`、粤语 `zh-HK-*`、台湾腔 `zh-TW-*`、东北话、陕西话
- 参数格式：语速 `+25%` / `-10%`，音调 `+2Hz`，音量 `+0%`

**两个实测坑（程序已处理）**：

1. edge-tts **不支持 SSML**，`<say-as>` 之类的标签会被**当字念出来**；也不支持 Azure 的 `style` 参数。
   所以程序内置了文本归一化：`98:95` → `98比95`、`45%` → `百分之45`、`12℃` → `12摄氏度`。
2. 微软文档里列的 `zh-CN-XiaomoNeural`、`Multilingual`、`DragonHD` 等音色在免费端点上**取不到**，只有 14 个。

想用更好的音质：选 `OpenAI 兼容 TTS API`，填 Base URL / Key / 模型与音色。

---

## 三、配视频源

| 类型 | 填什么 | 说明 |
| --- | --- | --- |
| 直播流 | `rtmp://...` / `http://...m3u8` / `http://...flv` / `rtsp://...` | 边播边解说；HLS/FLV 自动低延迟，断流自动重连，RTSP 自动走 TCP |
| 摄像头 | 下拉选设备 | Windows 用 DirectShow 枚举，未列出就点「重新扫描设备」 |
| 屏幕 | 留空 = 整个桌面，或 `1920x1080+0+0` | 解说屏幕/游戏画面 |
| 本地视频 | 填路径或用文件选择器上传 | 勾「按原速播放」= 模拟直播节奏；勾「循环播放」可长时间挂着 |

> 想解说 OBS 的画面：OBS 开「虚拟摄像头」，网页里选 `OBS Virtual Camera` 即可。

---

## 四、参数调优

| 参数 | 默认 | 建议 |
| --- | --- | --- |
| 解说间隔 | 4 秒 | 越小越实时但越贵/越慢。本地模型 4-6 秒；云端 API 4-8 秒 |
| 每次送几帧 | 4 帧 | 送得多更能看出动作连续性，token 线性增长 |
| 抓帧帧率 | 4 fps | 只是采样池，不影响成本 |
| 送模型高度 | 448 px | 降到 336 省约 45% token |
| 历史去重条数 | 4 | 让模型知道「刚说过什么」，避免复读机 |
| 跳过重复解说 | 开 | 画面静止时不重复配音（相似度 ≥ 90% 自动跳过） |

**成本估算**：一帧 ≈ `(高/28) × (宽/28)` 个视觉 token。448p、16:9、4 帧 ≈ 1800 token/次；
6 秒一次 ≈ 每小时 108 万 input token。想省钱：间隔 10 秒 + 2 帧 + 336p，约降到 1/6。

---

## 五、实测数据（RTX 4060 Laptop 8GB）

用 `qwen3-vl:4b-instruct` + edge-tts，输入是一段 NBA 比赛录像：

| 指标 | 实测值 |
| --- | --- |
| 显存占用 | 约 5.3GB（模型 3.1GB + 视觉编码器 + KV cache） |
| 首次调用 | 36 秒（含模型从磁盘加载进显存） |
| 后续每次推理 | **1.5 – 2.4 秒**（4 帧 448p 一起送） |
| 配音合成 | 1.2 – 1.8 秒/条 |
| 端到端解说延迟 | 约 4 – 8 秒 |

实际解说输出：

```
[0.9s]  夜幕下的丰田中心灯火辉煌，城市繁华尽收眼底。
[7.0s]  场馆内灯光璀璨，观众席上万众瞩目，气氛热烈。
[15.9s] 大屏上勇士与火箭的对决信息清晰呈现，现场氛围热烈。
```

模型能读出比分牌和场馆信息 —— 这不是模板，是真实推理结果。

---

## 六、项目结构

```
ai-live-commentary/
├─ install.bat / start.bat / 启动.bat   # Windows 一键安装与启动
├─ app/
│  ├─ main.py          # FastAPI 路由：配置、上传、会话、SSE 推送
│  ├─ config.py        # 配置模型 + 9 种解说风格提示词
│  ├─ capture.py       # ffmpeg 抓帧（文件/摄像头/屏幕/直播流 + 环形缓冲）
│  ├─ vlm.py           # 视觉后端：openai / ollama / transformers / 自检
│  ├─ tts.py           # 语音后端：edge-tts / OpenAI TTS / 关闭
│  ├─ pipeline.py      # 解说主循环：采样 → 提示词 → 生成 → 去重 → 配音
│  └─ static/          # 网页（原生 HTML/CSS/JS，无构建步骤）
├─ tests/
│  ├─ unit_test.py     # 离线单测（CI 跑这个）
│  ├─ smoke.py         # 抓帧 + 配音 + 文本清洗
│  ├─ e2e.py           # 端到端（支持 --openai / --ollama / --stream）
│  ├─ test_sources.py  # 单测某类输入源
│  └─ mock_openai.py   # 模拟 OpenAI 视觉 API，用来验证云端分支
└─ docs/provider-research.md
```

数据流：`抓帧线程 → 环形缓冲 → 解说循环取最近 N 帧 → 视觉模型 → 文本清洗/去重 → TTS → SSE → 网页`
（VLM 再慢也不会堆积延迟，因为循环永远只取最新帧）

---

## 七、HTTP API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/bootstrap` | 配置、音色、摄像头、风格预设 |
| POST | `/api/config` | 保存配置到 `config.json` |
| POST | `/api/test/vlm` · `/api/test/tts` | 连通性测试 |
| GET | `/api/ollama/models` | 列出本机 Ollama 模型 |
| POST | `/api/upload` | 上传本地视频 |
| POST | `/api/session/start` | 启动解说会话 |
| GET | `/api/session/{id}/events` | **SSE 实时流**：`frame` / `commentary` / `audio` / `status` / `error` / `stopped` |
| POST | `/api/session/{id}/stop` | 停止会话 |

```text
event: commentary
data: {"id":"ab12-3","t":12.4,"text":"库里三分线外出手，球进了！"}

event: audio
data: {"id":"ab12-3","mime":"audio/mpeg","data":"//uQxAAA..."}
```

---

## 八、测试

```bash
python tests/unit_test.py                  # 离线单测，无需任何外部依赖
python tests/smoke.py <你的视频.mp4>        # 抓帧 + edge-tts 配音 + 文本清洗
python tests/test_sources.py screen        # 屏幕捕获
python tests/test_sources.py stream <m3u8> # 直播流

python -m app.main                         # 另开一个窗口
python tests/e2e.py --ollama               # 端到端，走本机 Ollama
python tests/e2e.py --stream <m3u8>        # 端到端，走直播流
```

---

## 九、常见问题

| 现象 | 原因 / 处理 |
| --- | --- |
| 网页显示「视频源不可用」 | 地址写错或流需要鉴权；启动窗口里有 ffmpeg 的真实报错 |
| `exceed_context_size_error` | Ollama 上下文太小，填 `{"num_ctx": 6144}` 或减少帧数 |
| 视觉模型连续失败 3 次 | Ollama 没启动 / Key 错 / 余额不足 / 模型 ID 不对。点「测试连接」看报错 |
| `CUDA out of memory` | 降低送模型高度、加大间隔，或改用云端 API |
| 第一次解说等很久 | 本地模型首次加载进显存（实测 36 秒），之后每次 1.5-2.4 秒 |
| 没有声音 | 检查「开启语音播报」和右上角「播放语音」；浏览器需要先点一次页面才允许自动播放 |
| 解说老是重复 | 把「历史去重条数」调到 6-8，间隔调大，或换更强的模型 |
| 中文乱码（Windows） | 用 `start.bat` 启动（已设置 UTF-8）；自行运行 Python 时先 `set PYTHONUTF8=1` |

---

## 十、关于 LiveCC

[LiveCC](https://github.com/showlab/livecc) 是首个开源实时视频解说模型，基于 **Qwen2-VL-7B**，
用 500 万条视频-语音转录数据训练。它的门槛是：

1. 7B 全精度要 ~16GB 显存，8GB 显卡必须 4bit 量化 + 降分辨率；
2. 官方推理依赖 `flash-attn` 与 `liger-kernel`，Windows 上装不了（需 Linux + Triton），要改成 `sdpa`；
3. 训练语料以英文体育解说为主，中文输出不如中文原生视觉模型。

本项目把它作为 `本地 transformers` 后端的一个可选项保留。想获得更好的中文效果，建议用云端中文 VL 模型或本地 `qwen3-vl`。

---

## English TL;DR

**AI Live Commentary Workbench** — a configurable real-time video commentator.

- **Vision backends**: any OpenAI-compatible vision API, local Ollama, or local transformers (Qwen-VL / LiveCC).
- **TTS backends**: edge-tts (free Chinese voices), OpenAI-compatible TTS, or text-only.
- **Inputs**: live streams (RTMP / HLS / HTTP-FLV / RTSP), webcam, screen capture, local video files.
- **Output**: live commentary text over SSE + synthesized speech, plus TXT/SRT export.

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
python -m app.main        # open http://127.0.0.1:8848
```

UI is Chinese-first; the API is plain JSON + SSE, so wiring it into your own app is straightforward.

---

## License

[MIT](LICENSE)

LiveCC 及其权重、数据集版权归 [showlab](https://github.com/showlab/livecc) 所有；本项目仅调用其公开接口，不分发其权重。

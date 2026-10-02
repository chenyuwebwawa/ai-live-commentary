"""配置读写：所有后端参数都持久化在 config.json，网页里改完即存。"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get("LIVECC_CONFIG", ROOT / "config.json"))

DEFAULTS: dict = {
    "vlm": {
        "provider": "ollama",                     # ollama | openai | transformers | mock
        "base_url": "http://127.0.0.1:11434",
        "api_key": "",
        "model": "qwen3-vl:4b-instruct",
        "temperature": 0.8,
        "max_tokens": 80,
        "timeout": 300,
        "extra_body": {},                          # 例如 {"enable_thinking": false} / {"num_ctx": 6144}
        # --- 仅 transformers 后端使用 ---
        "local_path": "Qwen/Qwen3-VL-4B-Instruct",
        "load_in_4bit": True,
        "device": "cuda",
    },
    "tts": {
        "provider": "edge",                        # edge | openai | none
        "speak": True,
        "voice": "zh-CN-YunjianNeural",
        "rate": "+20%",
        "pitch": "+0Hz",
        "volume": "+0%",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "tts-1",
    },
    "source": {
        "type": "file",                            # file | camera | screen | stream
        "value": "",
        "realtime": True,                          # 文件是否按原速播放（模拟直播）
        "loop": False,
        "device_name": "",                         # 摄像头设备名
    },
    "commentary": {
        "style": "sports",
        "custom_prompt": "",
        "interval": 4.0,                           # 每隔几秒解说一次
        "frames_per_tick": 4,                      # 每次送给模型几帧
        "capture_fps": 4.0,                        # 抓帧帧率
        "frame_height": 448,                       # 送模型前的缩放高度
        "history_size": 4,                         # 附带几条历史解说用于去重
        "language": "zh",
        "dedupe": True,
    },
    "server": {"host": "127.0.0.1", "port": 8848},
}

STYLE_PRESETS: dict[str, dict[str, str]] = {
    "sports": {
        "name": "体育赛事解说",
        "prompt": (
            "你是一名激情澎湃的中文体育解说员，正在直播解说一场比赛。"
            "根据画面说出此刻正在发生的动作：谁在带球/投篮/进攻、比分或局势变化、精彩瞬间。"
            "语气紧凑、有节奏感，像真人解说一样，不要解说观众看不到的东西。"
        ),
    },
    "game": {
        "name": "游戏解说",
        "prompt": (
            "你是一名中文游戏解说，正在直播解说游戏画面。"
            "说明当前角色在做什么、地图位置、战斗或关键操作、局势优劣。"
            "用玩家熟悉的说法，短促有力，像直播弹幕风格但更专业。"
        ),
    },
    "documentary": {
        "name": "纪录片旁白",
        "prompt": (
            "你是一名纪录片旁白撰稿人。用平实、有画面感的中文描述画面中的人、物、环境与动作，"
            "语气克制从容，避免夸张形容词，不要抒情。"
        ),
    },
    "teaching": {
        "name": "教学讲解",
        "prompt": (
            "你是一名课程助教，正在为教学视频配解说。"
            "说清楚老师此刻在讲什么、板书或演示了什么步骤、屏幕上的关键内容，"
            "帮助学生跟上进度，语言简洁准确。"
        ),
    },
    "shopping": {
        "name": "带货直播",
        "prompt": (
            "你是一名中文带货主播。根据画面介绍正在展示的商品：外观、材质、使用场景和卖点，"
            "语气热情有感染力，像直播间的口播，不要编造画面里没有的参数。"
        ),
    },
    "meeting": {
        "name": "会议纪要",
        "prompt": (
            "你是一名会议记录员。用第三人称客观描述画面：谁在发言、展示了什么幻灯片或图表、"
            "屏幕上出现的关键数据，形成可检索的会议纪要句子。"
        ),
    },
    "accessibility": {
        "name": "无障碍画面描述",
        "prompt": (
            "你正在为视障用户实时描述视频画面。客观、准确、按重要性排序地描述："
            "场景、人物、正在发生的动作、画面上的文字信息。不加评论和情绪。"
        ),
    },
    "funny": {
        "name": "吐槽弹幕风",
        "prompt": (
            "你是一名幽默的中文吐槽UP主，用一句俏皮话点评画面里最值得吐槽的点，"
            "要有梗但不能冒犯真人，不要低俗。"
        ),
    },
    "custom": {"name": "自定义", "prompt": ""},
}

USER_PROMPT_TEMPLATE = (
    "这是视频最近的 {n} 帧画面，按时间顺序排列，覆盖大约 {span:.1f} 秒，"
    "当前播放位置约 {t:.1f} 秒。\n"
    "{history}"
    "请只针对**此刻最新的画面**说一句中文解说，要求：\n"
    "1. 只输出解说本身，一句话，不超过 40 个字；\n"
    "2. 不要重复上面已经解说过的内容，只讲新出现的变化；\n"
    "3. 不要出现“画面中”“我们可以看到”“这段视频”这类套话；\n"
    "4. 不要加引号、标题、序号、markdown。\n"
    "如果画面确实没有任何变化，就输出：画面保持静止。"
)


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return _deep_merge(DEFAULTS, saved)
        except Exception:
            pass
    return copy.deepcopy(DEFAULTS)


def save_config(cfg: dict) -> dict:
    merged = _deep_merge(DEFAULTS, cfg or {})
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def merge_config(cfg: dict) -> dict:
    """把外部传入的部分配置合并到默认值上，缺字段也不会崩。"""
    return _deep_merge(DEFAULTS, cfg or {})


def get_style_prompt(cfg: dict) -> str:
    style = cfg["commentary"].get("style", "sports")
    if style == "custom":
        return cfg["commentary"].get("custom_prompt") or STYLE_PRESETS["documentary"]["prompt"]
    return STYLE_PRESETS.get(style, STYLE_PRESETS["sports"])["prompt"]

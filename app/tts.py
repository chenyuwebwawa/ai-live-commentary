"""语音合成（TTS）适配层：edge-tts（免费中文音色）/ OpenAI 兼容 TTS / 关闭。

注意（实测结论）：
- edge-tts 不支持 SSML，也不支持 Azure 的 style 参数，标签会被当字念出来 —— 只能靠文本归一化；
- 免费 edge 端点只有 14 个中文音色，微软文档里那些 Multilingual / DragonHD / XiaomoNeural 取不到。
"""
from __future__ import annotations

import asyncio
import re

import httpx


def normalize_for_tts(text: str) -> str:
    """把比分、百分号等改成中文读法，避免"3:2"被念成"三冒号二"。"""
    text = re.sub(r"(?<![\d.])(\d{1,3})\s*[:：]\s*(\d{1,3})(?![\d])", r"\1比\2", text)
    text = re.sub(r"(?<![\d.])(\d+(?:\.\d+)?)\s*%", r"百分之\1", text)
    text = text.replace("℃", "摄氏度")
    return text


# edge-tts 中文音色（离线兜底清单，联网时会用 edge_tts.list_voices() 拉全量）
FALLBACK_VOICES = [
    {"name": "zh-CN-YunxiNeural", "gender": "男", "style": "阳光少年感，适合体育/游戏解说", "tags": "推荐"},
    {"name": "zh-CN-YunjianNeural", "gender": "男", "style": "浑厚有力，微软唯一 Sports 标签音色", "tags": "推荐"},
    {"name": "zh-CN-YunyangNeural", "gender": "男", "style": "专业播音腔，适合纪录片/新闻", "tags": ""},
    {"name": "zh-CN-YunxiaNeural", "gender": "男", "style": "少年音，适合游戏/二次元", "tags": ""},
    {"name": "zh-CN-XiaoxiaoNeural", "gender": "女", "style": "温暖自然，通用", "tags": "推荐"},
    {"name": "zh-CN-XiaoyiNeural", "gender": "女", "style": "活泼俏皮，适合带货/吐槽", "tags": ""},
    {"name": "zh-CN-liaoning-XiaobeiNeural", "gender": "女", "style": "东北话", "tags": ""},
    {"name": "zh-CN-shaanxi-XiaoniNeural", "gender": "女", "style": "陕西话", "tags": ""},
    {"name": "zh-HK-HiuMaanNeural", "gender": "女", "style": "粤语", "tags": ""},
    {"name": "zh-HK-HiuGaaiNeural", "gender": "女", "style": "粤语", "tags": ""},
    {"name": "zh-HK-WanLungNeural", "gender": "男", "style": "粤语", "tags": ""},
    {"name": "zh-TW-HsiaoChenNeural", "gender": "女", "style": "台湾腔", "tags": ""},
    {"name": "zh-TW-HsiaoYuNeural", "gender": "女", "style": "台湾腔", "tags": ""},
    {"name": "zh-TW-YunJheNeural", "gender": "男", "style": "台湾腔", "tags": ""},
]


class TTSError(RuntimeError):
    pass


class BaseTTS:
    label = "none"

    def __init__(self, cfg: dict):
        self.cfg = cfg or {}

    async def synth(self, text: str) -> tuple[bytes, str]:
        """返回 (音频字节, mime)。返回空字节表示跳过语音。"""
        return b"", ""

    async def test(self) -> tuple[bytes, str]:
        return await self.synth("测试一下语音合成效果。")


class NullTTS(BaseTTS):
    label = "none"


class EdgeTTS(BaseTTS):
    """微软 edge-tts：免费、无需 Key、不占显存。

    实测：连续调用时偶发 `NoAudioReceived`（服务端掐 websocket），属抖动而非配置错误，
    因此重试 2 次并把所有异常统一包成 TTSError，让上层跳过这一条而不是中断整个解说。
    """

    label = "edge"

    async def _stream_once(self, text: str, voice: str, kwargs: dict) -> bytes:
        import edge_tts

        try:
            communicate = edge_tts.Communicate(text, voice, **kwargs)
        except Exception:
            communicate = edge_tts.Communicate(text, voice)
        audio = bytearray()
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                audio.extend(chunk["data"])
        return bytes(audio)

    async def synth(self, text: str) -> tuple[bytes, str]:
        text = normalize_for_tts((text or "").strip())
        if not text:
            return b"", ""
        try:
            import edge_tts  # noqa: F401
        except ImportError as exc:
            raise TTSError("未安装 edge-tts：pip install edge-tts") from exc
        voice = self.cfg.get("voice") or "zh-CN-YunjianNeural"
        kwargs = {k: self.cfg[k] for k in ("rate", "volume", "pitch") if self.cfg.get(k)}
        last = ""
        for attempt in range(3):
            try:
                audio = await self._stream_once(text, voice, kwargs)
                if audio:
                    return audio, "audio/mpeg"
                last = "返回空音频"
            except Exception as exc:
                last = f"{type(exc).__name__}: {exc}"
            if attempt < 2:
                await asyncio.sleep(0.6 * (attempt + 1))
        raise TTSError(f"edge-tts 合成失败（已重试 3 次）：{last}")


class OpenAITTS(BaseTTS):
    label = "openai"

    async def synth(self, text: str) -> tuple[bytes, str]:
        text = (text or "").strip()
        if not text:
            return b"", ""
        base = (self.cfg.get("base_url") or "https://api.openai.com/v1").rstrip("/")
        url = base if base.endswith("/audio/speech") else base + "/audio/speech"
        headers = {"Content-Type": "application/json"}
        key = (self.cfg.get("api_key") or "").strip()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        payload = {
            "model": self.cfg.get("model") or "tts-1",
            "input": text,
            "voice": self.cfg.get("voice") or "alloy",
            "response_format": "mp3",
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except Exception as exc:
            raise TTSError(f"TTS 请求失败：{exc}") from exc
        if resp.status_code >= 400:
            raise TTSError(f"TTS HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.content, "audio/mpeg"


def build_tts(cfg: dict) -> BaseTTS:
    cfg = cfg or {}
    if not cfg.get("speak", True):
        return NullTTS(cfg)
    provider = cfg.get("provider", "edge")
    if provider == "edge":
        return EdgeTTS(cfg)
    if provider == "openai":
        return OpenAITTS(cfg)
    return NullTTS(cfg)


async def list_voices(provider: str = "edge") -> list[dict]:
    if provider != "edge":
        return []
    try:
        import edge_tts

        voices = await edge_tts.list_voices()
    except Exception:
        return FALLBACK_VOICES
    chinese = [
        {
            "name": v.get("ShortName"),
            "gender": "女" if v.get("Gender") == "Female" else "男",
            "style": (v.get("FriendlyName") or "").split(" - ")[-1],
            "tags": "",
        }
        for v in voices
        if str(v.get("Locale", "")).startswith(("zh-CN", "zh-HK", "zh-TW"))
    ]
    return chinese or FALLBACK_VOICES

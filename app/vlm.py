"""视觉理解模型（VLM）适配层：OpenAI 兼容云端 API / 本地 Ollama / 本地 transformers。

三种后端对外暴露同一个 describe() 接口，网页里切换即可，不用改代码。
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
from typing import Callable, Optional

import httpx
import numpy as np
from PIL import Image


class VLMError(RuntimeError):
    pass


def _jpeg_b64(frame: np.ndarray, quality: int = 82, max_side: int = 1280) -> str:
    img = Image.fromarray(frame[:, :, ::-1])  # BGR -> RGB
    if max(img.size) > max_side:
        scale = max_side / max(img.size)
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def frames_to_b64(frames: list[np.ndarray]) -> list[str]:
    return [_jpeg_b64(f) for f in frames]


def _join(base: str, suffix: str) -> str:
    base = (base or "").rstrip("/")
    if base.endswith(suffix.strip("/")):
        return base
    return base + "/" + suffix.lstrip("/")


async def _post_json(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload, headers=headers)
    if resp.status_code >= 400:
        body = resp.text[:600]
        raise VLMError(f"HTTP {resp.status_code} {url} -> {body}")
    try:
        return resp.json()
    except Exception as exc:
        raise VLMError(f"返回不是合法 JSON：{resp.text[:300]}") from exc


# --------------------------------------------------------------------------- #
class BaseVLM:
    label = "base"

    def __init__(self, cfg: dict, on_status: Optional[Callable[[str], None]] = None):
        self.cfg = cfg or {}
        self.on_status = on_status or (lambda _msg: None)

    def status(self, msg: str) -> None:
        self.on_status(msg)

    async def describe(self, frames: list[np.ndarray], prompt: str) -> str:
        raise NotImplementedError

    async def test(self) -> str:
        """用一张纯色图做连通性自检。"""
        img = np.zeros((64, 64, 3), dtype=np.uint8)
        img[:, :, 1] = 120
        return await self.describe([img], "用不超过 10 个字描述这张图片的颜色。")

    async def aclose(self) -> None:
        return None


# --------------------------------------------------------------------------- #
class OpenAICompatVLM(BaseVLM):
    """任何 OpenAI 兼容的 /chat/completions 视觉接口：
    阿里百炼 Qwen-VL、智谱 GLM-4V、硅基流动、Kimi、火山方舟、OpenRouter、OpenAI……
    """

    label = "openai-compatible"

    def _payload(self, frames: list[np.ndarray], prompt: str, token_field: str = "max_tokens") -> dict:
        content: list[dict] = [{"type": "text", "text": prompt}]
        for b64 in frames_to_b64(frames):
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        system = self.cfg.get("system_prompt")
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": content}
        ]
        payload = {
            "model": self.cfg.get("model"),
            "messages": messages,
            "temperature": float(self.cfg.get("temperature", 0.8)),
            token_field: int(self.cfg.get("max_tokens", 80) or 80),
        }
        extra = self.cfg.get("extra_body") or {}
        if isinstance(extra, dict):
            payload.update(extra)
        return payload

    async def describe(self, frames: list[np.ndarray], prompt: str) -> str:
        base = self.cfg.get("base_url") or "https://api.openai.com/v1"
        url = _join(base, "chat/completions")
        key = (self.cfg.get("api_key") or "").strip()
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        timeout = float(self.cfg.get("timeout", 60) or 60)
        try:
            data = await _post_json(url, self._payload(frames, prompt), headers, timeout)
        except VLMError as exc:
            # 部分新模型只认 max_completion_tokens
            if "max_tokens" in str(exc):
                data = await _post_json(url, self._payload(frames, prompt, "max_completion_tokens"), headers, timeout)
            else:
                raise
        try:
            msg = data["choices"][0]["message"]
            text = msg.get("content") or ""
            if isinstance(text, list):  # 少数服务返回分段内容
                text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
        except Exception as exc:
            raise VLMError(f"响应结构异常：{json.dumps(data, ensure_ascii=False)[:400]}") from exc
        return str(text).strip()


# --------------------------------------------------------------------------- #
class OllamaVLM(BaseVLM):
    """本地 Ollama，例如 qwen2.5vl:7b / qwen2.5vl:3b / minicpm-v / gemma3:4b。"""

    label = "ollama"

    @property
    def base(self) -> str:
        return (self.cfg.get("base_url") or "http://127.0.0.1:11434").rstrip("/")

    async def describe(self, frames: list[np.ndarray], prompt: str) -> str:
        options = {
            "temperature": float(self.cfg.get("temperature", 0.8)),
            "num_predict": int(self.cfg.get("max_tokens", 80) or 80),
            # 实测坑：Ollama 按显存自动给的 4096 上下文装不下 4 帧 448p 画面（约 4400 tokens），
            # 会直接报 exceed_context_size_error，所以这里显式放大。
            "num_ctx": int(self.cfg.get("num_ctx") or 8192),
        }
        extra = dict(self.cfg.get("extra_body") or {}) if isinstance(self.cfg.get("extra_body"), dict) else {}
        if isinstance(extra.get("options"), dict):
            options.update(extra.pop("options"))
        for key in ("num_ctx", "num_predict", "temperature", "top_p", "top_k", "repeat_penalty"):
            if key in extra:
                options[key] = extra.pop(key)
        payload = {
            "model": self.cfg.get("model") or "qwen3-vl:4b-instruct",
            # images 必须是「纯 base64 字符串」数组，不能带 data:image/jpeg;base64, 前缀
            "messages": [{"role": "user", "content": prompt, "images": frames_to_b64(frames)}],
            "stream": False,
            "keep_alive": self.cfg.get("keep_alive") or "30m",  # 常驻显存，避免每帧冷加载
            "options": options,
        }
        payload.update(extra)  # 其余键（如 {"think": false}）放到顶层
        timeout = float(self.cfg.get("timeout", 120) or 120)
        data = await _post_json(_join(self.base, "api/chat"), payload, {"Content-Type": "application/json"}, timeout)
        return str((data.get("message") or {}).get("content", "")).strip()

    @staticmethod
    async def list_models(base_url: str = "http://127.0.0.1:11434") -> dict:
        base = (base_url or "http://127.0.0.1:11434").rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                resp = await client.get(_join(base, "api/tags"))
            names = [m.get("name") for m in resp.json().get("models", [])]
            return {"online": True, "models": names}
        except Exception as exc:
            return {"online": False, "models": [], "error": str(exc)}


# --------------------------------------------------------------------------- #
class TransformersVLM(BaseVLM):
    """本地 transformers 推理（Qwen2.5-VL / Qwen2-VL / LiveCC-7B-Instruct 等）。
    模型只在第一次调用时加载，8GB 显存请打开 load_in_4bit。
    """

    label = "transformers"
    _cache: dict[str, tuple] = {}

    def _load(self):
        path = self.cfg.get("local_path") or ""
        if not path:
            raise VLMError("请填写本地模型路径或 HuggingFace 仓库名（例如 Qwen/Qwen2.5-VL-3B-Instruct）")
        if path in self._cache:
            return self._cache[path]
        self.status(f"正在加载本地模型 {path}（首次需要几分钟）…")
        try:
            import torch
            from transformers import AutoModelForImageTextToText, AutoProcessor
        except ImportError as exc:
            raise VLMError(
                "本地 transformers 后端还没装依赖。请执行：\n"
                "  D:\\AI\\live-commentary-venv\\Scripts\\python.exe -m pip install torch torchvision "
                "--index-url https://download.pytorch.org/whl/cu126\n"
                "  ... -m pip install transformers accelerate qwen-vl-utils bitsandbytes pillow-heif "
                "-i https://pypi.tuna.tsinghua.edu.cn/simple\n"
                f"（原始错误：{exc}）"
            ) from exc

        model_cls = AutoModelForImageTextToText
        kwargs: dict = {"torch_dtype": "auto", "device_map": self.cfg.get("device") or "cuda"}
        if self.cfg.get("load_in_4bit", True):
            try:
                from transformers import BitsAndBytesConfig

                kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=torch.bfloat16,
                )
            except Exception as exc:
                self.status(f"4bit 量化不可用（{exc}），改用全精度加载")
        model = model_cls.from_pretrained(path, **kwargs).eval()
        processor = AutoProcessor.from_pretrained(path)
        self._cache[path] = (model, processor)
        self.status(f"本地模型已就绪：{path}")
        return self._cache[path]

    def _generate(self, frames: list[np.ndarray], prompt: str) -> str:
        import torch

        model, processor = self._load()
        images = [Image.fromarray(f[:, :, ::-1]) for f in frames]
        content = []
        for img in images:
            content.append({"type": "image", "image": img})
        content.append({"type": "text", "text": prompt})
        messages = [{"role": "user", "content": content}]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        try:
            from qwen_vl_utils import process_vision_info

            image_inputs, video_inputs = process_vision_info(messages)
            inputs = processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt")
        except Exception:
            inputs = processor(text=[text], images=images, return_tensors="pt")
        inputs = {k: (v.to(model.device) if hasattr(v, "to") else v) for k, v in inputs.items()}
        temperature = float(self.cfg.get("temperature", 0.8) or 0.0)
        with torch.inference_mode():
            out = model.generate(
                **inputs,
                max_new_tokens=int(self.cfg.get("max_tokens", 80) or 80),
                do_sample=temperature > 0.01,
                temperature=max(temperature, 0.01),
            )
        trimmed = out[:, inputs["input_ids"].shape[1]:]
        return processor.batch_decode(trimmed, skip_special_tokens=True)[0].strip()

    async def describe(self, frames: list[np.ndarray], prompt: str) -> str:
        return await asyncio.to_thread(self._generate, frames, prompt)


# --------------------------------------------------------------------------- #
class MockVLM(BaseVLM):
    """自检用：不联网、不加载模型，用来验证采集→解说→配音→网页整条链路。"""

    label = "mock"

    async def describe(self, frames: list[np.ndarray], prompt: str) -> str:
        await asyncio.sleep(0.2)
        n = len(frames)
        return f"自检输出：收到 {n} 帧，第 {n} 帧平均亮度 {frames[-1].mean():.0f}。"


def build_vlm(cfg: dict, on_status: Optional[Callable[[str], None]] = None) -> BaseVLM:
    provider = (cfg or {}).get("provider", "openai")
    if provider == "ollama":
        return OllamaVLM(cfg, on_status)
    if provider == "transformers":
        return TransformersVLM(cfg, on_status)
    if provider == "mock":
        return MockVLM(cfg, on_status)
    return OpenAICompatVLM(cfg, on_status)

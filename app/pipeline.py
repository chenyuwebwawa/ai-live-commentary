"""解说流水线：抓帧 → 采样 → VLM 生成解说 → edge-tts 配音 → SSE 推给网页。"""
from __future__ import annotations

import asyncio
import base64
import difflib
import io
import time
import re
from typing import Any, Optional

import numpy as np
from PIL import Image

from .capture import FrameGrabber
from .config import USER_PROMPT_TEMPLATE, get_style_prompt
from .tts import BaseTTS, build_tts
from .vlm import BaseVLM, VLMError, build_vlm


def clean_commentary(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"^```.*?\n|```$", "", text, flags=re.S)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.S)      # **粗体**
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text, flags=re.S)  # *斜体*
    text = text.replace("**", "").replace("__", "").strip()
    text = re.sub(r"^\s*(?:[-*•]|\d+[.、)])\s*", "", text)        # 去掉列表符号
    text = text.replace("\n", " ").strip()
    text = re.sub(r'^[“"\'「【\[]+|[”"\'」】\]]+$', "", text).strip()
    return text[:150].strip()


class CommentarySession:
    """一次解说会话：一个视频源 + 一套模型配置，事件通过队列推给 SSE。"""

    def __init__(self, sid: str, cfg: dict):
        self.sid = sid
        self.cfg = cfg
        self.queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=200)
        self.grabber: Optional[FrameGrabber] = None
        self.vlm: Optional[BaseVLM] = None
        self.tts: Optional[BaseTTS] = None
        self.history: list[str] = []
        self.running = False
        self.started_at = time.time()
        self.tick = 0
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    # -- 事件 -------------------------------------------------------------- #
    def emit(self, event: dict) -> None:
        event.setdefault("ts", time.time())
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:  # 网页卡住时丢弃旧事件，保证不阻塞解说
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(event)
            except Exception:
                pass

    def status(self, text: str) -> None:
        self.emit({"type": "status", "text": text})

    def error(self, text: str) -> None:
        self.emit({"type": "error", "text": text})

    # -- 生命周期 ---------------------------------------------------------- #
    async def start(self) -> None:
        cfg = self.cfg
        src = cfg["source"]
        com = cfg["commentary"]
        self.status("正在启动采集…")
        self.grabber = FrameGrabber(
            src,
            cap_fps=float(com.get("capture_fps", 4) or 4),
            frame_height=int(com.get("frame_height", 448) or 448),
        )
        try:
            await asyncio.to_thread(self.grabber.start)
        except Exception as exc:
            raise RuntimeError(f"采集启动失败：{exc}") from exc
        self.status(f"采集已启动：{self.grabber.size[0]}x{self.grabber.size[1]} @ {self.grabber.cap_fps}fps")

        vlm_cfg = dict(cfg["vlm"])
        vlm_cfg["system_prompt"] = get_style_prompt(cfg)
        self.vlm = build_vlm(vlm_cfg, on_status=self.status)
        self.tts = build_tts(cfg["tts"])
        self.status(f"视觉模型：{self.vlm.label} · 语音：{'开' if self.tts.label != 'none' else '关'}")
        self.running = True
        self._task = asyncio.create_task(self._loop(), name=f"commentary-{self.sid}")

    async def stop(self) -> None:
        self._stop.set()
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        if self.grabber:
            await asyncio.to_thread(self.grabber.stop)
        if self.vlm:
            await self.vlm.aclose()
        self.status("已停止")

    # -- 主循环 ------------------------------------------------------------ #
    async def _loop(self) -> None:
        com = self.cfg["commentary"]
        interval = max(1.0, float(com.get("interval", 4) or 4))
        n_frames = max(1, int(com.get("frames_per_tick", 4) or 4))
        hist_size = max(0, int(com.get("history_size", 4) or 0))
        dedupe = bool(com.get("dedupe", True))
        speak = self.tts is not None and self.tts.label != "none"
        errors = 0
        try:
            while not self._stop.is_set():
                tick_start = time.monotonic()
                self.tick += 1
                if not self.grabber or not self.grabber.alive:
                    msg = self.grabber.error if self.grabber else "采集未启动"
                    self.error(f"视频源不可用或已结束：{msg}")
                    break
                frames = self.grabber.latest(n=n_frames, span=interval)
                if not frames:
                    self.status("等待第一帧…")
                    await asyncio.sleep(1)
                    continue
                now_t = frames[-1][0]
                self._emit_preview(frames[-1][1], now_t)

                prompt = self._build_prompt([f for _, f in frames], now_t, interval, hist_size)
                try:
                    raw = await self.vlm.describe([f for _, f in frames], prompt)
                    errors = 0
                except VLMError as exc:
                    errors += 1
                    self.error(f"视觉模型调用失败（第 {errors} 次）：{exc}")
                    if errors >= 3:
                        self.error("连续失败 3 次，会话结束。请检查模型配置后重试。")
                        break
                    await asyncio.sleep(interval)
                    continue

                text = clean_commentary(raw)
                if not text:
                    self.status("模型返回空内容，跳过")
                    await asyncio.sleep(interval)
                    continue

                if dedupe and self.history:
                    ratio = difflib.SequenceMatcher(None, text, self.history[-1]).ratio()
                    if ratio >= 0.9:
                        self.status(f"与上一条重复（相似度 {ratio:.0%}），已跳过：{text}")
                        await self._sleep_rest(tick_start, interval)
                        continue

                item_id = f"{self.sid}-{self.tick}"
                self.emit({"type": "commentary", "id": item_id, "t": round(now_t, 1), "text": text})
                self.history.append(text)
                if hist_size:
                    self.history = self.history[-hist_size:]

                if speak:
                    try:
                        audio, mime = await self.tts.synth(text)
                        if audio:
                            self.emit(
                                {
                                    "type": "audio",
                                    "id": item_id,
                                    "mime": mime or "audio/mpeg",
                                    "data": base64.b64encode(audio).decode("ascii"),
                                }
                            )
                    except Exception as exc:  # 配音失败不能影响文字解说
                        self.error(f"配音失败（不影响文字解说）：{type(exc).__name__}: {exc}")

                await self._sleep_rest(tick_start, interval)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover
            self.error(f"解说循环异常：{type(exc).__name__}: {exc}")
        finally:
            self.running = False
            self.emit({"type": "stopped"})

    async def _sleep_rest(self, tick_start: float, interval: float) -> None:
        rest = interval - (time.monotonic() - tick_start)
        if rest > 0:
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=rest)
            except asyncio.TimeoutError:
                pass

    # -- 辅助 -------------------------------------------------------------- #
    def _build_prompt(self, frames: list[np.ndarray], now_t: float, interval: float, hist_size: int) -> str:
        history_block = ""
        if hist_size and self.history:
            recent = self.history[-hist_size:]
            history_block = "已经解说过的内容（禁止重复）：\n" + "\n".join(f"- {h}" for h in recent) + "\n\n"
        return USER_PROMPT_TEMPLATE.format(
            n=len(frames), span=max(interval, 0.1), t=now_t, history=history_block
        )

    def _emit_preview(self, frame: np.ndarray, t: float) -> None:
        try:
            img = Image.fromarray(frame[:, :, ::-1])
            if max(img.size) > 640:
                scale = 640 / max(img.size)
                img = img.resize((int(img.width * scale), int(img.height * scale)), Image.BILINEAR)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=70)
            self.emit(
                {
                    "type": "frame",
                    "t": round(t, 1),
                    "mime": "image/jpeg",
                    "data": base64.b64encode(buf.getvalue()).decode("ascii"),
                }
            )
        except Exception:
            pass

    def info(self) -> dict[str, Any]:
        return {
            "id": self.sid,
            "running": self.running,
            "tick": self.tick,
            "elapsed": round(time.time() - self.started_at, 1),
            "history": self.history[-10:],
            "source": self.cfg["source"],
            "vlm": {"provider": self.cfg["vlm"].get("provider"), "model": self.cfg["vlm"].get("model")},
            "tts": {"provider": self.cfg["tts"].get("provider"), "voice": self.cfg["tts"].get("voice")},
            "grabber": {
                "frames_read": self.grabber.frames_read if self.grabber else 0,
                "error": self.grabber.error if self.grabber else "",
            },
        }

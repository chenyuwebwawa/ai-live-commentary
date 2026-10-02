"""FastAPI 服务：配置页 + 解说会话（SSE 实时推送）。"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from pathlib import Path

# 国内网络：GitHub / HuggingFace 常被屏蔽，默认走镜像（用户已设则不覆盖）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .capture import ffmpeg_version, list_cameras
from .config import CONFIG_PATH, DEFAULTS, STYLE_PRESETS, load_config, merge_config, save_config
from .pipeline import CommentarySession
from .tts import FALLBACK_VOICES, build_tts, list_voices
from .vlm import OllamaVLM, build_vlm

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="AI 自动解说工作台", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

SESSIONS: dict[str, CommentarySession] = {}


class ConfigBody(BaseModel):
    config: dict


class StartBody(BaseModel):
    config: dict


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(STATIC / "index.html"))


@app.get("/api/bootstrap")
async def bootstrap() -> dict:
    """一次性返回页面初始化所需的全部信息。"""
    cfg = load_config()
    return {
        "config": cfg,
        "defaults": DEFAULTS,
        "styles": STYLE_PRESETS,
        "voices": await list_voices("edge"),
        "fallback_voices": FALLBACK_VOICES,
        "cameras": await asyncio.to_thread(list_cameras),
        "ffmpeg": ffmpeg_version(),
        "config_path": str(CONFIG_PATH),
    }


@app.post("/api/config")
async def api_save_config(body: ConfigBody) -> dict:
    return {"ok": True, "config": save_config(body.config)}


@app.get("/api/ollama/models")
async def api_ollama_models(base_url: str = "http://127.0.0.1:11434") -> dict:
    return await OllamaVLM.list_models(base_url)


@app.post("/api/test/vlm")
async def api_test_vlm(body: ConfigBody) -> dict:
    cfg = dict(body.config or {})
    client = build_vlm(cfg)
    started = time.time()
    try:
        text = await asyncio.wait_for(client.test(), timeout=float(cfg.get("timeout", 60) or 60) + 30)
        return {"ok": True, "latency": round(time.time() - started, 2), "reply": text}
    except Exception as exc:
        return JSONResponse(status_code=200, content={"ok": False, "error": f"{type(exc).__name__}: {exc}"})
    finally:
        await client.aclose()


@app.post("/api/test/tts")
async def api_test_tts(body: ConfigBody) -> dict:
    import base64

    cfg = dict(body.config or {})
    client = build_tts(cfg)
    started = time.time()
    try:
        audio, mime = await client.test()
        return {
            "ok": bool(audio),
            "latency": round(time.time() - started, 2),
            "mime": mime,
            "audio": base64.b64encode(audio).decode("ascii"),
            "error": "" if audio else "未产生音频（可能已关闭语音）",
        }
    except Exception as exc:
        return JSONResponse(status_code=200, content={"ok": False, "error": f"{type(exc).__name__}: {exc}"})


@app.get("/api/cameras")
async def api_cameras() -> dict:
    return {"cameras": await asyncio.to_thread(list_cameras)}


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)) -> dict:
    """把本地视频上传/复制到工作目录，返回可被 ffmpeg 读取的绝对路径。"""
    uploads = ROOT / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    safe = Path(file.filename or "video.mp4").name.replace("..", "_")
    target = uploads / f"{int(time.time())}_{safe}"
    size = 0
    with target.open("wb") as fh:
        while True:
            chunk = await file.read(1 << 20)
            if not chunk:
                break
            size += len(chunk)
            fh.write(chunk)
    return {"ok": True, "path": str(target), "size": size}


@app.post("/api/session/start")
async def api_start(body: StartBody) -> dict:
    cfg = merge_config(body.config or {})   # 缺字段补默认值，避免老配置/半截配置把会话搞崩
    sid = uuid.uuid4().hex[:8]
    session = CommentarySession(sid, cfg)
    try:
        await session.start()
    except Exception as exc:
        await session.stop()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    SESSIONS[sid] = session
    return {"ok": True, "session_id": sid}


@app.get("/api/session/{sid}/events")
async def api_events(sid: str, request: Request) -> StreamingResponse:
    session = SESSIONS.get(sid)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    async def gen():
        try:
            yield "retry: 3000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(session.queue.get(), timeout=10)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    if not session.running and session.queue.empty():
                        break
                    continue
                etype = event.pop("type", "message")
                yield f"event: {etype}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                if etype == "stopped":
                    break
        finally:
            if session.running:
                await session.stop()
            SESSIONS.pop(sid, None)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.post("/api/session/{sid}/stop")
async def api_stop(sid: str) -> dict:
    session = SESSIONS.get(sid)
    if not session:
        return {"ok": True, "note": "会话已不存在"}
    await session.stop()
    return {"ok": True}


@app.get("/api/session/{sid}")
async def api_info(sid: str) -> dict:
    session = SESSIONS.get(sid)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session.info()


@app.get("/api/sessions")
async def api_sessions() -> dict:
    return {"sessions": [s.info() for s in SESSIONS.values()]}


def main() -> None:
    import uvicorn

    cfg = load_config()
    host = cfg["server"].get("host", "127.0.0.1")
    port = int(cfg["server"].get("port", 8848))
    print(f"\n  AI 自动解说工作台  ->  http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

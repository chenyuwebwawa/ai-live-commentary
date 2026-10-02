"""模拟一个 OpenAI 兼容的视觉 API，用来验证「云端 API」这条代码路径。

它会检查请求体是否符合 OpenAI 视觉接口规范（messages + image_url data URL），
然后返回一句伪造的解说。这样即使没有 API Key 也能测通云端分支。

用法：
    python tests/mock_openai.py            # 监听 127.0.0.1:8899
    python tests/e2e.py --openai           # 另开窗口跑端到端
"""
from __future__ import annotations

import sys
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()
CALLS: list[dict] = []


@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    msgs = body.get("messages") or []
    images = 0
    texts = []
    for m in msgs:
        content = m.get("content")
        if isinstance(content, list):
            for part in content:
                if part.get("type") == "image_url":
                    url = (part.get("image_url") or {}).get("url", "")
                    assert url.startswith("data:image/jpeg;base64,"), f"图片格式不对: {url[:40]}"
                    images += 1
                elif part.get("type") == "text":
                    texts.append(part.get("text", ""))
    CALLS.append({"model": body.get("model"), "images": images, "max_tokens": body.get("max_tokens"),
                  "extra": {k: v for k, v in body.items() if k not in ("messages", "model")}})
    print(f"[mock] 收到请求 #{len(CALLS)}: model={body.get('model')} 图片={images} 提示词={len(texts[0]) if texts else 0}字 "
          f"max_tokens={body.get('max_tokens')} extra_keys={list(CALLS[-1]['extra'])}", flush=True)
    if images == 0:
        return JSONResponse(status_code=400, content={"error": {"message": "no image provided"}})
    return {
        "id": "mock-1",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": f'"模拟解说：第 {len(CALLS)} 次调用，收到 {images} 帧画面。"'},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": images * 450, "completion_tokens": 20, "total_tokens": images * 450 + 20},
    }


@app.get("/stats")
async def stats():
    return {"calls": len(CALLS), "detail": CALLS}


if __name__ == "__main__":
    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    print(f"mock OpenAI 视觉 API -> http://127.0.0.1:{port}/v1", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

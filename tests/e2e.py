"""端到端测试：启动服务后用「自检模式 VLM + edge-tts」跑一个真实视频源，验证 SSE 全链路。

前置：先启动服务   python -m app.main
用法：
    python tests/e2e.py                       # 默认用本地视频文件
    python tests/e2e.py <视频路径>
    python tests/e2e.py --stream <流地址>      # 验证直播流输入
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx

from _video import default_video  # noqa: E402  (tests/ 目录自身加入 sys.path)

BASE = "http://127.0.0.1:8848"

_argv = sys.argv[1:]
_rest = [a for a in _argv if not a.startswith("--")]
if "--stream" in _argv:
    _i = _argv.index("--stream")
    _url = _argv[_i + 1] if len(_argv) > _i + 1 else "http://127.0.0.1:8899/index.m3u8"
    SOURCE = {"type": "stream", "value": _url, "realtime": True, "loop": False}
else:
    VIDEO = default_video(_rest[0] if _rest else None)
    SOURCE = {"type": "file", "value": VIDEO, "realtime": True, "loop": False}

# --openai：把视觉后端切成「云端 API」分支，指向 tests/mock_openai.py 起的模拟服务
# --ollama：用本机真实 Ollama 视觉模型跑（最接近实际使用）
if "--ollama" in _argv:
    VLM = {"provider": "ollama", "base_url": "http://127.0.0.1:11434", "model": "qwen3-vl:4b-instruct",
           "temperature": 0.8, "max_tokens": 80, "timeout": 300}
elif "--openai" in _argv:
    VLM = {"provider": "openai", "base_url": "http://127.0.0.1:8899/v1", "api_key": "sk-mock",
           "model": "mock-vl", "temperature": 0.8, "max_tokens": 60, "timeout": 30,
           "extra_body": {"enable_thinking": False}}
else:
    VLM = {"provider": "mock", "model": "mock", "temperature": 0, "max_tokens": 40, "timeout": 30}
INTERVAL = 6.0 if "--ollama" in _argv else 2.0


def main() -> int:
    cfg = {
        "vlm": VLM,
        "tts": {"provider": "edge", "speak": True, "voice": "zh-CN-YunxiNeural", "rate": "+12%"},
        "source": SOURCE,
        "commentary": {
            "style": "sports", "custom_prompt": "", "interval": INTERVAL, "frames_per_tick": 4,
            "capture_fps": 4.0, "frame_height": 448, "history_size": 4, "dedupe": False,
        },
    }
    boot = httpx.get(f"{BASE}/api/bootstrap", timeout=30).json()
    print(f"bootstrap: ffmpeg={boot['ffmpeg'][:40]}... cameras={boot['cameras']} voices={len(boot['voices'])}")

    r = httpx.post(f"{BASE}/api/session/start", json={"config": cfg}, timeout=60)
    print(f"start -> {r.status_code} {r.text[:200]}")
    if r.status_code != 200:
        return 1
    sid = r.json()["session_id"]

    counts: dict[str, int] = {}
    errors: list[str] = []
    texts: list[tuple[float, str]] = []
    audio_bytes = 0
    frames = 0
    t0 = time.time()

    try:
        with httpx.stream("GET", f"{BASE}/api/session/{sid}/events", timeout=httpx.Timeout(90, read=60)) as stream:
            etype = None
            for line in stream.iter_lines():
                if line.startswith("event: "):
                    etype = line[len("event: "):].strip()
                elif line.startswith("data: ") and etype:
                    data = json.loads(line[len("data: "):])
                    counts[etype] = counts.get(etype, 0) + 1
                    if etype == "commentary":
                        texts.append((data["t"], data["text"]))
                        print(f"  [{data['t']}s] {data['text']}")
                    elif etype == "audio":
                        import base64
                        audio_bytes += len(base64.b64decode(data["data"]))
                    elif etype == "frame":
                        frames += 1
                        if frames == 1:
                            print(f"  首帧: {len(data['data'])} 字节 base64, t={data['t']}s")
                    elif etype == "error":
                        errors.append(data["text"])
                        print(f"  [错误] {data['text']}")
                    elif etype == "stopped":
                        print("  会话结束")
                        break
                if len(texts) >= 3 and counts.get("audio", 0) >= 3 and frames >= 3:
                    break
                if time.time() - t0 > 90:
                    print("  超时退出")
                    break
    finally:
        try:
            httpx.post(f"{BASE}/api/session/{sid}/stop", timeout=15)
        except Exception:
            pass

    print(f"\n事件统计: {counts}  配音总字节={audio_bytes}  耗时={time.time()-t0:.1f}s")
    ok = True
    for name, need in (("frame", 3), ("commentary", 3), ("audio", 3)):
        if counts.get(name, 0) < need:
            print(f"[FAIL] {name} 事件不足（{counts.get(name,0)} < {need}）")
            ok = False
    if errors:
        print(f"[FAIL] 出现 {len(errors)} 条错误：{errors[:2]}")
        ok = False
    if audio_bytes < 5000:
        print("[FAIL] 音频数据过少")
        ok = False
    print("\n端到端全链路通过 ✔" if ok else "\n端到端测试失败 ✘")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

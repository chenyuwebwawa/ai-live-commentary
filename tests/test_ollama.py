"""用本机 Ollama 视觉模型做一次真实解说推理（不需要任何 API Key）。

用法：python tests/test_ollama.py [模型名] [视频路径]
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.capture import FrameGrabber  # noqa: E402
from app.config import USER_PROMPT_TEMPLATE, get_style_prompt  # noqa: E402
from app.tts import EdgeTTS  # noqa: E402
from app.vlm import OllamaVLM  # noqa: E402
from _video import default_video  # noqa: E402

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen3-vl:4b-instruct"
VIDEO = default_video(sys.argv[2] if len(sys.argv) > 2 else None)


async def main() -> int:
    info = await OllamaVLM.list_models()
    print(f"Ollama 在线={info['online']}  模型={info.get('models')}")
    if not info["online"]:
        print("Ollama 没在运行，请先启动（开始菜单打开 Ollama，或运行 ollama serve）")
        return 1
    if MODEL not in (info.get("models") or []) and f"{MODEL}:latest" not in (info.get("models") or []):
        print(f"[警告] 本机没找到模型 {MODEL}，仍尝试调用（Ollama 会自动报错）")

    grabber = FrameGrabber({"type": "file", "value": VIDEO, "realtime": True}, cap_fps=4, frame_height=448)
    grabber.start()
    t0 = time.time()
    while grabber.frames_read < 8 and time.time() - t0 < 20:
        time.sleep(0.2)
    frames = grabber.latest(n=4, span=2.0)
    grabber.stop()
    print(f"取到 {len(frames)} 帧，尺寸 {frames[-1][1].shape if frames else None}")

    vlm = OllamaVLM({
        "provider": "ollama", "model": MODEL, "base_url": "http://127.0.0.1:11434",
        "temperature": 0.8, "max_tokens": 80, "timeout": 300,
        "system_prompt": get_style_prompt({"commentary": {"style": "sports", "custom_prompt": ""}}),
    })
    prompt = USER_PROMPT_TEMPLATE.format(n=len(frames), span=2.0, t=2.0, history="")

    print(f"\n[第 1 次调用]（首次会加载模型到显存，可能 30-90 秒）")
    t1 = time.time()
    text = await vlm.describe([f for _, f in frames], prompt)
    t_first = time.time() - t1
    print(f"  耗时 {t_first:.1f}s -> {text}")

    print(f"\n[第 2 次调用]（模型已在显存，看真实推理速度）")
    t2 = time.time()
    text2 = await vlm.describe([f for _, f in frames], prompt)
    t_second = time.time() - t2
    print(f"  耗时 {t_second:.1f}s -> {text2}")

    print(f"\n[配音]")
    t3 = time.time()
    audio, mime = await EdgeTTS({"voice": "zh-CN-YunjianNeural", "rate": "+20%"}).synth(text2 or text or "测试")
    print(f"  耗时 {time.time()-t3:.1f}s -> {len(audio)} 字节 {mime}")

    print(f"\n结论：首次 {t_first:.1f}s、后续 {t_second:.1f}s/次；配音 {len(audio)} 字节。")
    print(f"建议解说间隔 ≥ {max(4, round(t_second + 1))} 秒。")
    ok = bool((text or text2).strip())
    print("本机 Ollama 视觉解说链路通过 ✔" if ok else "模型返回空内容 ✘")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

"""离线冒烟测试：不依赖任何 API Key，验证 ffmpeg 抓帧 + edge-tts 配音 + 流水线取帧。

用法：
    D:\\AI\\live-commentary-venv\\Scripts\\python.exe tests\\smoke.py [视频路径]
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # Windows 控制台默认 GBK，避免中文/符号报错
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.capture import FrameGrabber, ffmpeg_version, list_cameras  # noqa: E402
from app.pipeline import clean_commentary  # noqa: E402
from app.tts import EdgeTTS, normalize_for_tts  # noqa: E402
from _video import default_video  # noqa: E402

OK, FAIL = "[PASS]", "[FAIL]"
failures = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global failures
    print(f"{OK if cond else FAIL} {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures += 1


def test_capture(video: str) -> None:
    print("\n--- 1. 抓帧 ---")
    grabber = FrameGrabber(
        {"type": "file", "value": video, "realtime": True, "loop": False},
        cap_fps=4.0,
        frame_height=448,
    )
    t0 = time.time()
    grabber.start()
    print(f"     源尺寸(缩放后)={grabber.size} 帧字节={grabber.frame_size}")
    while grabber.frames_read < 8 and time.time() - t0 < 15:
        time.sleep(0.2)
    frames = grabber.latest(n=4, span=1.5)
    elapsed = time.time() - t0
    check("ffmpeg 抓帧", grabber.frames_read >= 8, f"{grabber.frames_read} 帧 / {elapsed:.1f}s")
    check("环形缓冲取最近 4 帧", len(frames) == 4, f"取得 {len(frames)} 帧")
    if frames:
        frame = frames[-1][1]
        check("帧尺寸正确", frame.shape == (grabber.size[1], grabber.size[0], 3), str(frame.shape))
    grabber.stop()
    check("ffmpeg 进程已回收", not grabber.alive)


def test_tts() -> None:
    print("\n--- 2. edge-tts 配音 ---")
    tts = EdgeTTS({"voice": "zh-CN-YunxiNeural", "rate": "+12%", "pitch": "+0Hz", "volume": "+0%"})
    t0 = time.time()
    try:
        audio, mime = asyncio.run(tts.synth("球进了！三分命中，比分反超。"))
    except Exception as exc:
        check("edge-tts 合成", False, f"{type(exc).__name__}: {exc}")
        return
    check("edge-tts 合成", len(audio) > 2000, f"{len(audio)} 字节 / {time.time()-t0:.1f}s / {mime}")


def test_clean() -> None:
    print("\n--- 3. 文本清洗 ---")
    cases = [
        ('"球员突破上篮得分。"', "球员突破上篮得分。"),
        ("1. 画面中出现进球。", "画面中出现进球。"),
        ("- 有人在投篮\n", "有人在投篮"),
        ("**精彩瞬间**", "精彩瞬间"),
    ]
    for raw, want in cases:
        got = clean_commentary(raw)
        check(f"清洗 {raw!r}", got == want, f"-> {got!r}")

    print("\n--- 4. 语音文本归一化（edge-tts 不支持 SSML）---")
    for raw, want in [
        ("比分 98:95", "比分 98比95"),
        ("命中率 45%", "命中率 百分之45"),
        ("温度 12℃", "温度 12摄氏度"),
        ("开场 2026-10-02 结束", "开场 2026-10-02 结束"),
        ("球进了！", "球进了！"),
    ]:
        got = normalize_for_tts(raw)
        check(f"归一化 {raw!r}", got == want, f"-> {got!r}")


def main() -> int:
    video = default_video(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"ffmpeg: {ffmpeg_version()}")
    print(f"摄像头: {list_cameras() or '未检测到'}")
    print(f"测试视频: {video}  存在={os.path.exists(video)}")
    if not os.path.exists(video):
        print("找不到测试视频，跳过抓帧测试")
        return 1
    test_capture(video)
    test_tts()
    test_clean()
    print(f"\n{'全部通过 ✔' if not failures else f'{failures} 项失败 ✘'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

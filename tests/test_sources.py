"""输入源通道测试：屏幕捕获 / 直播流（HLS）。

用法：
    python tests/test_sources.py screen
    python tests/test_sources.py stream http://127.0.0.1:8899/index.m3u8
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.capture import FrameGrabber  # noqa: E402


def run(source: dict, seconds: float = 6.0, want: int = 6) -> int:
    g = FrameGrabber(source, cap_fps=4.0, frame_height=448)
    t0 = time.time()
    try:
        g.start()
    except Exception as exc:
        print(f"[FAIL] 启动失败：{exc}")
        return 1
    print(f"     缩放后尺寸={g.size}")
    while g.frames_read < want and time.time() - t0 < seconds:
        time.sleep(0.2)
    frames = g.latest(n=4, span=1.5)
    print(f"     读到 {g.frames_read} 帧 / {time.time()-t0:.1f}s，取最近 {len(frames)} 帧，error={g.error!r}")
    g.stop()
    ok = g.frames_read >= want
    print("[PASS] 抓帧成功" if ok else "[FAIL] 帧数不足")
    return 0 if ok else 1


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "screen"
    if mode == "screen":
        region = sys.argv[2] if len(sys.argv) > 2 else ""
        print(f"--- 屏幕捕获 (region={region or '整个桌面'}) ---")
        return run({"type": "screen", "value": region})
    if mode == "stream":
        url = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8899/index.m3u8"
        print(f"--- 直播流 {url} ---")
        return run({"type": "stream", "value": url}, seconds=20.0)
    print(f"未知模式：{mode}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

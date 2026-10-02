"""测试用视频解析：命令行参数 > 环境变量 LIVECC_TEST_VIDEO > samples/ 下的任意 mp4。"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"


def default_video(argv_value: str | None = None) -> str:
    if argv_value:
        return argv_value
    env = os.environ.get("LIVECC_TEST_VIDEO")
    if env and Path(env).exists():
        return env
    named = SAMPLES / "demo-vlog.mp4"
    if named.exists():
        return str(named)
    if SAMPLES.is_dir():
        for f in sorted(SAMPLES.glob("*.mp4")):
            return str(f)
    raise SystemExit(
        "找不到测试视频。三种办法任选：\n"
        "  1) python tests/xxx.py <你的视频路径>\n"
        "  2) 设置环境变量 LIVECC_TEST_VIDEO=D:\\videos\\demo.mp4\n"
        f"  3) 把任意 mp4 放到 {SAMPLES}\\ 下\n"
    )

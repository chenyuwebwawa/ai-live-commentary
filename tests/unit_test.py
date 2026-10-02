"""纯离线单元测试：不联网、不需要 ffmpeg/GPU/模型，CI 里跑这个。

    python tests/unit_test.py        # 直接跑
    pytest tests/unit_test.py        # 或用 pytest
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DEFAULTS, STYLE_PRESETS, get_style_prompt, merge_config  # noqa: E402
from app.pipeline import clean_commentary  # noqa: E402
from app.tts import FALLBACK_VOICES, normalize_for_tts  # noqa: E402
from app.vlm import MockVLM, OllamaVLM, OpenAICompatVLM, TransformersVLM, build_vlm  # noqa: E402


# --------------------------------------------------------------------------- #
def test_clean_commentary():
    cases = [
        ('"球员突破上篮得分。"', "球员突破上篮得分。"),
        ("1. 画面中出现进球。", "画面中出现进球。"),
        ("- 有人在投篮\n", "有人在投篮"),
        ("**精彩瞬间**", "精彩瞬间"),
        ("```\n门将扑出点球\n```", "门将扑出点球"),
        ("「好球！」", "好球！"),
    ]
    for raw, want in cases:
        got = clean_commentary(raw)
        assert got == want, f"{raw!r} -> {got!r}，期望 {want!r}"


def test_clean_commentary_truncates():
    assert len(clean_commentary("啊" * 500)) <= 150


def test_normalize_for_tts():
    cases = [
        ("比分 98:95", "比分 98比95"),
        ("命中率 45%", "命中率 百分之45"),
        ("温度 12℃", "温度 12摄氏度"),
        ("开场 2026-10-02 结束", "开场 2026-10-02 结束"),   # 日期不能被误改
        ("球进了！", "球进了！"),
    ]
    for raw, want in cases:
        got = normalize_for_tts(raw)
        assert got == want, f"{raw!r} -> {got!r}，期望 {want!r}"


def test_merge_config_fills_defaults():
    merged = merge_config({"commentary": {"interval": 7}})
    assert merged["commentary"]["interval"] == 7
    assert merged["commentary"]["frames_per_tick"] == DEFAULTS["commentary"]["frames_per_tick"]
    assert merged["vlm"]["provider"] == DEFAULTS["vlm"]["provider"]
    assert merge_config({})["server"]["port"] == DEFAULTS["server"]["port"]


def test_style_prompts():
    for key, preset in STYLE_PRESETS.items():
        assert preset["name"], key
        if key != "custom":
            prompt = get_style_prompt({"commentary": {"style": key}})
            assert len(prompt) > 20, key
    custom = get_style_prompt({"commentary": {"style": "custom", "custom_prompt": "只说动作"}})
    assert custom == "只说动作"
    # 自定义为空时回落到默认风格，不能返回空串
    assert get_style_prompt({"commentary": {"style": "custom", "custom_prompt": ""}})


def test_build_vlm_dispatch():
    assert isinstance(build_vlm({"provider": "ollama"}), OllamaVLM)
    assert isinstance(build_vlm({"provider": "openai"}), OpenAICompatVLM)
    assert isinstance(build_vlm({"provider": "transformers"}), TransformersVLM)
    assert isinstance(build_vlm({"provider": "mock"}), MockVLM)


def test_fallback_voices_are_edge_names():
    assert len(FALLBACK_VOICES) >= 10
    for v in FALLBACK_VOICES:
        assert v["name"].startswith(("zh-CN-", "zh-HK-", "zh-TW-")), v["name"]
        assert v["gender"] in ("男", "女")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"[PASS] {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"[FAIL] {fn.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过" + ("" if not failed else f"，{failed} 项失败"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

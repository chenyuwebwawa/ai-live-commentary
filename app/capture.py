"""视频帧采集：用 ffmpeg 子进程统一处理 文件 / 摄像头 / 屏幕 / 直播流 四种输入。

设计要点：
- ffmpeg 输出 rawvideo(bgr24) 到 stdout，后台线程读帧进环形缓冲；
- 解说线程按需从缓冲里取"最近 N 帧"，因此 VLM 再慢也不会堆积延迟；
- ffmpeg 的 stderr 单独收集，出错时能在网页上看到真实原因。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from collections import deque
from typing import Optional

import numpy as np

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


# --------------------------------------------------------------------------- #
# ffmpeg 定位
# --------------------------------------------------------------------------- #
def ffmpeg_path() -> str:
    env = os.environ.get("FFMPEG_BIN")
    if env and os.path.exists(env):
        return env
    for cand in (r"D:\AI\ffmpeg\bin\ffmpeg.exe", r"C:\ffmpeg\bin\ffmpeg.exe"):
        if os.path.exists(cand):
            return cand
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:  # pip 包 imageio-ffmpeg 自带一份可执行文件
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "找不到 ffmpeg。请安装 imageio-ffmpeg（pip install imageio-ffmpeg），"
            "或把 ffmpeg.exe 放到 D:\\AI\\ffmpeg\\bin\\，或设置环境变量 FFMPEG_BIN。"
        ) from exc


def ffmpeg_version() -> str:
    try:
        out = subprocess.run(
            [ffmpeg_path(), "-version"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=CREATE_NO_WINDOW,
        ).stdout
        return out.splitlines()[0] if out else "unknown"
    except Exception as exc:
        return f"unavailable: {exc}"


def list_cameras() -> list[str]:
    """枚举 Windows 摄像头（DirectShow 设备名）。"""
    if os.name != "nt":
        return []
    try:
        proc = subprocess.run(
            [ffmpeg_path(), "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            capture_output=True,
            timeout=25,
            creationflags=CREATE_NO_WINDOW,
        )
        text = proc.stderr.decode("utf-8", errors="ignore")
    except Exception:
        return []
    return re.findall(r'"([^"]+)"\s*\(video\)', text)


# --------------------------------------------------------------------------- #
# 输入参数拼装
# --------------------------------------------------------------------------- #
def _ffprobe_path() -> Optional[str]:
    exe = ffmpeg_path()
    cand = os.path.join(os.path.dirname(exe), "ffprobe.exe" if os.name == "nt" else "ffprobe")
    if os.path.exists(cand):
        return cand
    return shutil.which("ffprobe")


def _probe_size(source: dict) -> tuple[int, int]:
    """探测源分辨率，用于计算 scale 后的固定宽度（rawvideo 必须知道帧长）。

    优先用 ffprobe（只读文件头，几百毫秒）；不可用时退回 ffmpeg 解一帧到 null。
    """
    args, _ = _input_args(source, 0)
    probe = _ffprobe_path()
    if probe:
        try:
            proc = subprocess.run(
                [probe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                 "-of", "csv=p=0:s=x"] + args,
                capture_output=True,
                timeout=20,
                creationflags=CREATE_NO_WINDOW,
            )
            text = proc.stdout.decode("utf-8", errors="ignore").strip()
            m = re.match(r"^(\d{2,5})x(\d{2,5})", text)
            if m:
                w, h = int(m.group(1)), int(m.group(2))
                if 16 <= w <= 8192 and 16 <= h <= 8192:
                    return w, h
        except Exception:
            pass
    try:
        proc = subprocess.run(
            [ffmpeg_path(), "-hide_banner"] + args + ["-frames:v", "1", "-f", "null", "-"],
            capture_output=True,
            timeout=25,
            creationflags=CREATE_NO_WINDOW,
        )
        text = proc.stderr.decode("utf-8", errors="ignore")
        m = re.findall(r"(\d{2,5})x(\d{2,5})", text)
        if m:
            w, h = int(m[-1][0]), int(m[-1][1])
            if 16 <= w <= 8192 and 16 <= h <= 8192:
                return w, h
    except Exception:
        pass
    return 1280, 720


def _input_args(source: dict, cap_fps: float) -> tuple[list[str], list[str]]:
    """返回 (输入参数, 附加输出参数)。"""
    stype = (source.get("type") or "file").lower()
    value = (source.get("value") or "").strip()
    realtime = bool(source.get("realtime", True))
    fps = max(1.0, float(cap_fps or 4))

    if stype == "file":
        if not value or not os.path.exists(value):
            raise RuntimeError(f"视频文件不存在：{value}")
        args = ["-stream_loop", "-1"] if source.get("loop") else []
        if realtime:
            args += ["-re"]
        return args + ["-i", value], []

    if stype == "stream":
        if not value:
            raise RuntimeError("请填写直播流地址（rtmp:// / http://....m3u8 / .flv）")
        args = [
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-probesize", "500000",
            "-analyzeduration", "1000000",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
        ]
        if value.lower().startswith("rtsp://"):
            args = ["-rtsp_transport", "tcp"] + args
        if ".m3u8" in value.lower():
            args += ["-live_start_index", "-1"]
        return args + ["-i", value], []

    if stype == "camera":
        name = value or source.get("device_name") or ""
        if not name:
            raise RuntimeError("请选择摄像头设备（网页里会列出本机可用设备）")
        return ["-f", "dshow", "-framerate", str(int(fps)), "-i", f"video={name}"], []

    if stype == "screen":
        region = []
        if value and re.match(r"^\d+x\d+\+\d+\+\d+$", value):
            w, h, x, y = re.split(r"[x+]", value)
            region = ["-video_size", f"{w}x{h}", "-offset_x", x, "-offset_y", y]
        return ["-f", "gdigrab", "-framerate", str(int(fps))] + region + ["-i", "desktop"], []

    raise RuntimeError(f"不支持的输入源类型：{stype}")


# --------------------------------------------------------------------------- #
# 抓帧器
# --------------------------------------------------------------------------- #
class FrameGrabber:
    """后台抓帧，维护一个 (时间戳, BGR帧) 的环形缓冲。"""

    def __init__(self, source: dict, cap_fps: float = 4.0, frame_height: int = 448, buffer_seconds: float = 30.0):
        self.source = dict(source or {})
        self.cap_fps = max(1.0, float(cap_fps or 4))
        self.frame_height = int(frame_height or 448)
        self._buf: deque[tuple[float, np.ndarray]] = deque(maxlen=int(self.cap_fps * buffer_seconds) + 8)
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.frame_size = 0
        self.size = (0, 0)
        self.frames_read = 0
        self.start_time = 0.0
        self.error = ""
        self.ended = False

    # -- 生命周期 ---------------------------------------------------------- #
    def start(self) -> None:
        args, _ = _input_args(self.source, self.cap_fps)
        src_w, src_h = _probe_size(self.source)
        out_h = self.frame_height if self.frame_height % 2 == 0 else self.frame_height + 1
        out_w = max(2, int(round(out_h * src_w / max(src_h, 1) / 2.0)) * 2)
        self.size = (out_w, out_h)
        self.frame_size = out_w * out_h * 3
        vf = f"fps={self.cap_fps},scale={out_w}:{out_h}"
        cmd = [ffmpeg_path(), "-hide_banner", "-loglevel", "warning", "-nostdin"] + args + [
            "-vf", vf, "-an", "-sn", "-f", "rawvideo", "-pix_fmt", "bgr24", "-",
        ]
        self._cmd = cmd
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=self.frame_size * 2,
            creationflags=CREATE_NO_WINDOW,
        )
        self.start_time = time.time()
        self._thread = threading.Thread(target=self._read_loop, name="frame-reader", daemon=True)
        self._thread.start()
        self._stderr_thread = threading.Thread(target=self._drain_stderr, name="ffmpeg-stderr", daemon=True)
        self._stderr_thread.start()

    def stop(self) -> None:
        self._stop.set()
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass
        for t in (self._thread, self._stderr_thread):
            if t and t.is_alive():
                t.join(timeout=3)

    # -- 内部线程 ---------------------------------------------------------- #
    def _drain_stderr(self) -> None:
        proc = self._proc
        if not proc or not proc.stderr:
            return
        lines: deque[str] = deque(maxlen=40)
        try:
            for raw in iter(proc.stderr.readline, b""):
                line = raw.decode("utf-8", errors="ignore").strip()
                if line:
                    lines.append(line)
                    if "error" in line.lower() or "failed" in line.lower() or "invalid" in line.lower():
                        self.error = line
        except Exception:
            pass
        if not self.error and lines:
            self.error = lines[-1]

    def _read_loop(self) -> None:
        proc = self._proc
        assert proc and proc.stdout
        stream = proc.stdout
        buf = bytearray(self.frame_size)
        view = memoryview(buf)
        while not self._stop.is_set():
            got = 0
            while got < self.frame_size:
                chunk = stream.read(self.frame_size - got)
                if not chunk:
                    self.ended = True
                    if not self.error:
                        self.error = "视频源已结束或中断"
                    return
                view[got:got + len(chunk)] = chunk
                got += len(chunk)
            frame = np.frombuffer(bytes(buf), dtype=np.uint8).reshape(self.size[1], self.size[0], 3).copy()
            with self._lock:
                self._buf.append((time.time() - self.start_time, frame))
                self.frames_read += 1

    # -- 取帧 -------------------------------------------------------------- #
    def latest(self, n: int = 4, span: Optional[float] = None) -> list[tuple[float, np.ndarray]]:
        """取最近 n 帧，尽量均匀铺满 span 秒。"""
        with self._lock:
            items = list(self._buf)
        if not items:
            return []
        n = max(1, int(n))
        if len(items) <= n:
            return items
        if span:
            newest_t = items[-1][0]
            window = [it for it in items if it[0] >= newest_t - float(span)]
            items = window if len(window) >= n else items[-n:]
        if len(items) <= n:
            return items
        idx = np.linspace(0, len(items) - 1, n).round().astype(int)
        return [items[i] for i in dict.fromkeys(idx.tolist())]

    def snapshot(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._buf[-1][1] if self._buf else None

    @property
    def alive(self) -> bool:
        return bool(self._proc) and self._proc.poll() is None and not self.ended

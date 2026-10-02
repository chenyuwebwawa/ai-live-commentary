/* AI 自动解说工作台 —— 前端逻辑 */
(() => {
  const $ = (id) => document.getElementById(id);
  let BOOT = null;
  let ES = null;
  let SID = null;
  const records = [];               // {t, text}
  const audioQueue = [];
  let audioPlaying = false;
  const sourceCache = { stream: "", camera: "", screen: "", file: "" };

  // ---------------------------------------------------------------- 工具
  const setOut = (el, ok, msg) => {
    el.className = "test-out " + (ok ? "ok" : "err");
    el.textContent = msg;
  };
  const status = (text, kind = "idle") => {
    const pill = $("status-pill");
    pill.textContent = text;
    pill.className = "pill " + (kind === "run" ? "pill-run" : kind === "err" ? "pill-err" : "pill-idle");
  };
  const addBubble = (cls, meta, text, audio) => {
    const feed = $("feed");
    const empty = feed.querySelector(".feed-empty");
    if (empty) empty.remove();
    const el = document.createElement("div");
    el.className = "bubble " + cls;
    el.innerHTML = `<div class="meta"><span>${meta}</span><span class="tools"></span></div><div class="text"></div>`;
    el.querySelector(".text").textContent = text;
    const tools = el.querySelector(".tools");
    if (audio) {
      el.dataset.audio = audio.data;
      el.dataset.mime = audio.mime;
      const btn = document.createElement("button");
      btn.className = "replay";
      btn.textContent = "🔊 重播";
      btn.onclick = () => playAudio(audio.data, audio.mime);
      tools.appendChild(btn);
    }
    feed.appendChild(el);
    feed.scrollTop = feed.scrollHeight;
    while (feed.children.length > 300) feed.removeChild(feed.firstChild);
    return el;
  };

  // ---------------------------------------------------------------- 音频
  function playAudio(b64, mime) {
    const audio = new Audio(`data:${mime};base64,${b64}`);
    audio.play().catch((e) => console.warn("播放失败", e));
  }
  function enqueueAudio(b64, mime) {
    if (!$("audio-enabled").checked) return;
    audioQueue.push({ b64, mime });
    pumpAudio();
  }
  function pumpAudio() {
    if (audioPlaying || !audioQueue.length) return;
    const item = audioQueue.shift();
    if (!$("audio-enabled").checked) return pumpAudio();
    audioPlaying = true;
    const audio = new Audio(`data:${item.mime};base64,${item.b64}`);
    audio.onended = audio.onerror = () => { audioPlaying = false; pumpAudio(); };
    audio.play().catch(() => { audioPlaying = false; pumpAudio(); });
  }

  // ---------------------------------------------------------------- 表单
  function fillForm(cfg) {
    $("vlm-provider").value = cfg.vlm.provider || "openai";
    $("vlm-base-url").value = cfg.vlm.base_url || "";
    $("vlm-api-key").value = cfg.vlm.api_key || "";
    $("vlm-model").value = cfg.vlm.model || "";
    $("vlm-extra-body").value = Object.keys(cfg.vlm.extra_body || {}).length
      ? JSON.stringify(cfg.vlm.extra_body) : "";
    $("vlm-ollama-url").value = cfg.vlm.provider === "ollama" && cfg.vlm.base_url
      ? cfg.vlm.base_url : "http://127.0.0.1:11434";
    $("vlm-ollama-model").value = cfg.vlm.provider === "ollama" ? cfg.vlm.model : "qwen3-vl:4b-instruct";
    $("vlm-local-path").value = cfg.vlm.local_path || "";
    $("vlm-4bit").checked = !!cfg.vlm.load_in_4bit;
    $("vlm-device").value = cfg.vlm.device || "cuda";
    $("vlm-temperature").value = cfg.vlm.temperature;
    $("vlm-max-tokens").value = cfg.vlm.max_tokens;
    $("vlm-timeout").value = cfg.vlm.timeout;

    $("tts-speak").checked = !!cfg.tts.speak;
    $("tts-provider").value = cfg.tts.provider || "edge";
    $("tts-rate").value = cfg.tts.rate || "";
    $("tts-pitch").value = cfg.tts.pitch || "";
    $("tts-volume").value = cfg.tts.volume || "";
    $("tts-base-url").value = cfg.tts.base_url || "";
    $("tts-api-key").value = cfg.tts.api_key || "";
    $("tts-model").value = cfg.tts.model || "";
    $("tts-oai-voice").value = cfg.tts.provider === "openai" ? cfg.tts.voice : "alloy";

    $("src-type").value = cfg.source.type || "stream";
    $("src-realtime").checked = cfg.source.realtime !== false;
    $("src-loop").checked = !!cfg.source.loop;
    sourceCache.stream = cfg.source.type === "stream" ? cfg.source.value || "" : "";
    sourceCache.camera = cfg.source.type === "camera" ? cfg.source.value || "" : "";
    sourceCache.screen = cfg.source.type === "screen" ? cfg.source.value || "" : "";
    sourceCache.file = cfg.source.type === "file" ? cfg.source.value || "" : "";
    $("src-stream-url").value = sourceCache.stream;
    $("src-screen-region").value = sourceCache.screen;
    $("src-file-path").value = sourceCache.file;
    $("src-realtime").checked = cfg.source.realtime !== false;

    $("cm-style").value = cfg.commentary.style || "sports";
    $("cm-custom-prompt").value = cfg.commentary.custom_prompt || "";
    $("cm-interval").value = cfg.commentary.interval;
    $("cm-frames").value = cfg.commentary.frames_per_tick;
    $("cm-capture-fps").value = cfg.commentary.capture_fps;
    $("cm-frame-height").value = cfg.commentary.frame_height;
    $("cm-history").value = cfg.commentary.history_size;
    $("cm-dedupe").checked = !!cfg.commentary.dedupe;

    const sel = $("tts-voice");
    sel.innerHTML = "";
    (BOOT.voices || []).forEach((v) => {
      const o = document.createElement("option");
      o.value = v.name;
      o.textContent = `${v.name}（${v.gender}${v.tags ? " · " + v.tags : ""}）${v.style ? " " + v.style : ""}`;
      sel.appendChild(o);
    });
    if (cfg.tts.voice) {
      if (![...sel.options].some((o) => o.value === cfg.tts.voice)) {
        const o = document.createElement("option");
        o.value = cfg.tts.voice; o.textContent = cfg.tts.voice;
        sel.appendChild(o);
      }
      sel.value = cfg.tts.voice;
    }

    const cam = $("src-device");
    cam.innerHTML = "";
    (BOOT.cameras || []).forEach((c) => {
      const o = document.createElement("option");
      o.value = c; o.textContent = c;
      cam.appendChild(o);
    });
    if (!(BOOT.cameras || []).length) {
      const o = document.createElement("option");
      o.value = ""; o.textContent = "（未检测到摄像头）";
      cam.appendChild(o);
    }
    if (sourceCache.camera) cam.value = sourceCache.camera;

    const styleSel = $("cm-style");
    styleSel.innerHTML = "";
    Object.entries(BOOT.styles || {}).forEach(([k, v]) => {
      const o = document.createElement("option");
      o.value = k; o.textContent = v.name;
      styleSel.appendChild(o);
    });
    styleSel.value = cfg.commentary.style || "sports";

    $("preset-hint").innerHTML = "常用：阿里百炼 <code>https://dashscope.aliyuncs.com/compatible-mode/v1</code>"
      + " · 智谱 <code>https://open.bigmodel.cn/api/paas/v4</code>"
      + " · 硅基流动 <code>https://api.siliconflow.cn/v1</code>";
    applyVisibility();
  }

  function applyVisibility() {
    const map = {
      vlm: $("vlm-provider").value,
      tts: $("tts-provider").value,
      src: $("src-type").value,
    };
    document.querySelectorAll("[data-when]").forEach((el) => {
      const [k, v] = el.dataset.when.split("=");
      el.style.display = map[k] === v ? "" : "none";
    });
  }

  function collect() {
    const vlmProvider = $("vlm-provider").value;
    const ttsProvider = $("tts-provider").value;
    const srcType = $("src-type").value;
    let extra = {};
    const extraRaw = $("vlm-extra-body").value.trim();
    if (extraRaw) { try { extra = JSON.parse(extraRaw); } catch (e) { throw new Error("额外参数不是合法 JSON"); } }

    if (srcType === "stream") sourceCache.stream = $("src-stream-url").value.trim();
    if (srcType === "camera") sourceCache.camera = $("src-device").value;
    if (srcType === "screen") sourceCache.screen = $("src-screen-region").value.trim();
    if (srcType === "file") sourceCache.file = $("src-file-path").value.trim();

    return {
      vlm: {
        provider: vlmProvider,
        base_url: vlmProvider === "ollama" ? $("vlm-ollama-url").value.trim()
          : vlmProvider === "transformers" ? "" : $("vlm-base-url").value.trim(),
        api_key: $("vlm-api-key").value.trim(),
        model: vlmProvider === "ollama" ? $("vlm-ollama-model").value.trim() : $("vlm-model").value.trim(),
        local_path: $("vlm-local-path").value.trim(),
        load_in_4bit: $("vlm-4bit").checked,
        device: $("vlm-device").value.trim() || "cuda",
        temperature: parseFloat($("vlm-temperature").value || "0.8"),
        max_tokens: parseInt($("vlm-max-tokens").value || "80", 10),
        timeout: parseFloat($("vlm-timeout").value || "60"),
        extra_body: extra,
      },
      tts: {
        provider: ttsProvider,
        speak: $("tts-speak").checked,
        voice: ttsProvider === "edge" ? $("tts-voice").value : $("tts-oai-voice").value.trim(),
        rate: $("tts-rate").value.trim(),
        pitch: $("tts-pitch").value.trim(),
        volume: $("tts-volume").value.trim(),
        base_url: $("tts-base-url").value.trim(),
        api_key: $("tts-api-key").value.trim(),
        model: $("tts-model").value.trim(),
      },
      source: {
        type: srcType,
        value: sourceCache[srcType] || "",
        realtime: $("src-realtime").checked,
        loop: $("src-loop").checked,
      },
      commentary: {
        style: $("cm-style").value,
        custom_prompt: $("cm-custom-prompt").value.trim(),
        interval: parseFloat($("cm-interval").value || "4"),
        frames_per_tick: parseInt($("cm-frames").value || "4", 10),
        capture_fps: parseFloat($("cm-capture-fps").value || "4"),
        frame_height: parseInt($("cm-frame-height").value || "448", 10),
        history_size: parseInt($("cm-history").value || "4", 10),
        dedupe: $("cm-dedupe").checked,
        language: "zh",
      },
      server: BOOT.config.server,
    };
  }

  // ---------------------------------------------------------------- 会话
  async function start() {
    let cfg;
    try { cfg = collect(); } catch (e) { setOut($("vlm-test-out"), false, e.message); return; }
    status("启动中…", "run");
    $("btn-start").disabled = true;
    try {
      const r = await fetch("/api/session/start", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config: cfg }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "启动失败");
      SID = data.session_id;
      $("btn-stop").disabled = false;
      attach(SID);
    } catch (e) {
      status("启动失败", "err");
      addBubble("err", "错误", String(e.message || e));
      $("btn-start").disabled = false;
    }
  }

  function attach(sid) {
    if (ES) ES.close();
    ES = new EventSource(`/api/session/${sid}/events`);
    ES.addEventListener("status", (ev) => {
      const d = JSON.parse(ev.data);
      addBubble("status", "状态", d.text);
      status(d.text.slice(0, 18), "run");
    });
    ES.addEventListener("error", (ev) => {
      if (!ev.data) { status("连接中断", "err"); return; }
      const d = JSON.parse(ev.data);
      addBubble("err", "错误", d.text);
    });
    ES.addEventListener("frame", (ev) => {
      const d = JSON.parse(ev.data);
      const img = $("preview-img");
      img.src = `data:${d.mime};base64,${d.data}`;
      img.classList.add("show");
      $("preview-empty").style.display = "none";
      $("preview-time").textContent = `${d.t}s`;
      $("frame-count").textContent = (parseInt($("frame-count").textContent, 10) || 0) + 1;
    });
    ES.addEventListener("commentary", (ev) => {
      const d = JSON.parse(ev.data);
      records.push({ t: d.t, text: d.text });
      const el = addBubble("audio-pending", `⏱ ${d.t}s`, d.text);
      el.id = "c-" + d.id;
      status("解说中", "run");
    });
    ES.addEventListener("audio", (ev) => {
      const d = JSON.parse(ev.data);
      const el = document.getElementById("c-" + d.id);
      if (el) {
        el.classList.remove("audio-pending");
        el.dataset.audio = d.data;
        el.dataset.mime = d.mime;
        const btn = document.createElement("button");
        btn.className = "replay"; btn.textContent = "🔊 重播";
        btn.onclick = () => playAudio(d.data, d.mime);
        el.querySelector(".tools").appendChild(btn);
        if (!$("audio-enabled").checked) return;
      }
      enqueueAudio(d.data, d.mime);
    });
    ES.addEventListener("stopped", () => { closeSession(); });
    ES.onerror = () => { if (ES && ES.readyState === EventSource.CLOSED) closeSession(); };
  }

  function closeSession() {
    if (ES) { ES.close(); ES = null; }
    SID = null;
    $("btn-start").disabled = false;
    $("btn-stop").disabled = true;
    status("已停止");
  }

  async function stop() {
    if (SID) { try { await fetch(`/api/session/${SID}/stop`, { method: "POST" }); } catch (e) {} }
    closeSession();
  }

  // ---------------------------------------------------------------- 导出
  const pad = (n, w = 2) => String(n).padStart(w, "0");
  const srtTime = (s) => {
    const ms = Math.floor((s % 1) * 1000), t = Math.floor(s);
    return `${pad(Math.floor(t / 3600))}:${pad(Math.floor(t / 60) % 60)}:${pad(t % 60)},${pad(ms, 3)}`;
  };
  function download(name, text) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
    a.download = name; a.click(); URL.revokeObjectURL(a.href);
  }

  // ---------------------------------------------------------------- 事件
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.onclick = () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tabpane").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      document.querySelector(`.tabpane[data-pane="${tab.dataset.tab}"]`).classList.add("active");
    };
  });
  ["vlm-provider", "tts-provider", "src-type"].forEach((id) => {
    $(id).addEventListener("change", applyVisibility);
  });

  $("btn-save").onclick = async () => {
    try {
      const cfg = collect();
      const r = await fetch("/api/config", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config: cfg }),
      });
      const d = await r.json();
      $("save-note").textContent = `已保存到 ${BOOT.config_path}`;
      setTimeout(() => ($("save-note").textContent = ""), 4000);
      BOOT.config = d.config;
    } catch (e) { $("save-note").textContent = "保存失败：" + e.message; }
  };

  $("btn-test-vlm").onclick = async () => {
    setOut($("vlm-test-out"), true, "测试中…（本地模型首次加载较慢）");
    $("btn-test-vlm").disabled = true;
    try {
      const r = await fetch("/api/test/vlm", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config: collect().vlm }),
      });
      const d = await r.json();
      setOut($("vlm-test-out"), d.ok, d.ok ? `✅ 连通，耗时 ${d.latency}s，模型回复：${d.reply}` : `❌ ${d.error}`);
    } catch (e) { setOut($("vlm-test-out"), false, "❌ " + e.message); }
    $("btn-test-vlm").disabled = false;
  };

  $("btn-test-tts").onclick = async () => {
    setOut($("tts-test-out"), true, "合成中…");
    try {
      const r = await fetch("/api/test/tts", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config: collect().tts }),
      });
      const d = await r.json();
      if (d.ok) { setOut($("tts-test-out"), true, `✅ 合成成功，耗时 ${d.latency}s`); playAudio(d.audio, d.mime); }
      else setOut($("tts-test-out"), false, "❌ " + (d.error || "失败"));
    } catch (e) { setOut($("tts-test-out"), false, "❌ " + e.message); }
  };

  $("btn-ollama-scan").onclick = async () => {
    const base = $("vlm-ollama-url").value.trim() || "http://127.0.0.1:11434";
    setOut($("vlm-test-out"), true, "检测中…");
    try {
      const r = await fetch(`/api/ollama/models?base_url=${encodeURIComponent(base)}`);
      const d = await r.json();
      const dl = $("ollama-models");
      dl.innerHTML = "";
      (d.models || []).forEach((m) => { const o = document.createElement("option"); o.value = m; dl.appendChild(o); });
      setOut($("vlm-test-out"), d.online,
        d.online ? `✅ Ollama 在线，${d.models.length} 个模型：\n${(d.models || []).join("\n") || "（还没有模型，先 ollama pull qwen2.5vl:7b）"}`
                 : `❌ 连不上 Ollama：${d.error || ""}`);
    } catch (e) { setOut($("vlm-test-out"), false, "❌ " + e.message); }
  };

  $("btn-scan-cam").onclick = async () => {
    const r = await fetch("/api/cameras");
    const d = await r.json();
    const sel = $("src-device");
    sel.innerHTML = "";
    (d.cameras || []).forEach((c) => { const o = document.createElement("option"); o.value = c; o.textContent = c; sel.appendChild(o); });
    if (!(d.cameras || []).length) {
      const o = document.createElement("option"); o.value = ""; o.textContent = "（未检测到摄像头）"; sel.appendChild(o);
    }
  };

  $("src-file-upload").onchange = async (ev) => {
    const file = ev.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    $("src-file-path").value = "上传中…";
    try {
      const r = await fetch("/api/upload", { method: "POST", body: fd });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "上传失败");
      $("src-file-path").value = d.path;
      sourceCache.file = d.path;
    } catch (e) { $("src-file-path").value = "上传失败：" + e.message; }
  };

  $("btn-start").onclick = start;
  $("btn-stop").onclick = stop;
  $("btn-clear").onclick = () => {
    $("feed").innerHTML = '<div class="feed-empty">开始后，解说会一条条出现在这里，并自动配音。</div>';
    records.length = 0;
  };
  $("btn-export-txt").onclick = () => {
    if (!records.length) return alert("还没有解说内容");
    download("live-commentary.txt", records.map((r) => `[${r.t}s] ${r.text}`).join("\n"));
  };
  $("btn-export-srt").onclick = () => {
    if (!records.length) return alert("还没有解说内容");
    const srt = records.map((r, i) => `${i + 1}\n${srtTime(r.t)} --> ${srtTime(r.t + 3)}\n${r.text}\n`).join("\n");
    download("live-commentary.srt", srt);
  };

  // ---------------------------------------------------------------- 初始化
  (async () => {
    try {
      const r = await fetch("/api/bootstrap");
      BOOT = await r.json();
      fillForm(BOOT.config);
      status("未开始");
      addBubble("status", "环境", `ffmpeg：${BOOT.ffmpeg}\n摄像头：${(BOOT.cameras || []).join(" / ") || "未检测到"}`);
    } catch (e) {
      addBubble("err", "初始化失败", String(e));
    }
  })();
})();

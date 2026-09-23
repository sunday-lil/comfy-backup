# -*- coding: utf-8 -*-
"""下载 Qwen2.5-7B GGUF 分片并导入 Ollama（替代被墙的 ollama pull）"""
import os, time, requests, subprocess

BASE = r"D:\ollama_models"
URL = "https://modelscope.cn/models/qwen/Qwen2.5-7B-Instruct-GGUF/resolve/master"
LOG = r"D:\comfyui_workflows-main\setup\logs\qwen_import.log"
FILES = ["qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf", "qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf"]

def log(m):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {m}\n")

def dl(name):
    dest = os.path.join(BASE, name)
    for attempt in range(1, 100):
        try:
            pos = os.path.getsize(dest) if os.path.exists(dest) else 0
            h = {"User-Agent": "Mozilla/5.0"}
            if pos:
                h["Range"] = f"bytes={pos}-"
            with requests.get(f"{URL}/{name}", headers=h, stream=True, timeout=(30, 60)) as r:
                r.raise_for_status()
                mode = "ab" if pos and r.status_code == 206 else "wb"
                total = int(r.headers.get("Content-Length", 0)) + (pos if mode == "ab" else 0)
                with open(dest, mode) as f:
                    for c in r.iter_content(1024 * 1024):
                        f.write(c)
            if os.path.getsize(dest) >= total:
                log(f"DONE {name} {os.path.getsize(dest)/1073741824:.2f}GB")
                return True
        except Exception as e:
            log(f"RETRY({attempt}) {name}: {e}")
            time.sleep(10)
    return False

os.makedirs(BASE, exist_ok=True)
for n in FILES:
    if not dl(n):
        log(f"FAIL {n}")
        raise SystemExit(1)

# 写 Modelfile 并导入
mf = os.path.join(BASE, "Modelfile")
with open(mf, "w", encoding="utf-8") as f:
    f.write(f"FROM ./{FILES[0]}\n")
log("开始 ollama create qwen2.5:7b")
r = subprocess.run(["ollama", "create", "qwen2.5:7b", "-f", mf], capture_output=True, text=True, timeout=600)
log(f"create exit={r.returncode} {r.stdout[-200:]} {r.stderr[-200:]}")
r2 = subprocess.run(["ollama", "list"], capture_output=True, text=True)
log(f"ollama list: {r2.stdout}")

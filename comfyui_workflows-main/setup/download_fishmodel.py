# -*- coding: utf-8 -*-
"""从 ModelScope 下载 openaudio-s1-mini 模型到 fish-speech checkpoints"""
import os, time, requests

BASE = r"D:\fish-speech-main\checkpoints\openaudio-s1-mini"
URL = "https://modelscope.cn/models/fishaudio/openaudio-s1-mini/resolve/master"
LOG = r"D:\comfy\comfyui_workflows-main\setup\logs\fish_install.log"
UA = {"User-Agent": "Mozilla/5.0"}
FILES = [
    ("model.pth", 1735122974),
    ("codec.pth", 1871099728),
    ("config.json", 844),
    ("special_tokens.json", 126275),
    ("tokenizer.tiktoken", 2561218),
]

def log(m):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {m}\n")
    print(m)

def dl(name, expect):
    dest = os.path.join(BASE, name)
    os.makedirs(BASE, exist_ok=True)
    attempt = 0
    while True:
        attempt += 1
        try:
            pos = os.path.getsize(dest) if os.path.exists(dest) else 0
            if pos == expect:
                log(f"SKIP {name} 已完成")
                return True
            if pos > expect:
                os.remove(dest)
                pos = 0
            h = {**UA}
            if pos:
                h["Range"] = f"bytes={pos}-"
            with requests.get(f"{URL}/{name}", headers=h, stream=True, timeout=(30, 60), allow_redirects=True) as r:
                if r.status_code == 416:
                    return os.path.getsize(dest) == expect
                r.raise_for_status()
                mode = "ab" if pos and r.status_code == 206 else "wb"
                if mode == "wb":
                    pos = 0
                with open(dest, mode) as f:
                    for chunk in r.iter_content(1024 * 1024):
                        f.write(chunk)
                        pos += len(chunk)
            if os.path.getsize(dest) == expect:
                log(f"DONE {name} {expect/1073741824:.2f}GB 尝试{attempt}次")
                return True
            raise RuntimeError(f"不完整 {os.path.getsize(dest)}/{expect}")
        except Exception as e:
            log(f"RETRY({attempt}) {name}: {type(e).__name__} {str(e)[:80]}")
            time.sleep(min(10 * attempt, 60))

ok = all(dl(n, e) for n, e in FILES)
log(f"模型下载{'全部完成' if ok else '失败'}")
print("OK" if ok else "FAIL")

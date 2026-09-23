# -*- coding: utf-8 -*-
"""下载并安装 ffmpeg 到 D:\ffmpeg，加入用户 PATH（健壮版：精确校验大小+无限重试）"""
import os, sys, time, zipfile, subprocess, winreg
import requests

URL = "https://ghfast.top/https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip"
DEST = r"D:\ffmpeg_zip\ffmpeg.zip"
EXTRACT = r"D:\ffmpeg_zip"
FINAL = r"D:\ffmpeg"
LOG = r"D:\comfy\comfyui_workflows-main\setup\logs\ffmpeg_install.log"
UA = {"User-Agent": "Mozilla/5.0"}

def log(m):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {m}\n")

def remote_size(url):
    r = requests.get(url, headers={**UA, "Range": "bytes=0-0"}, timeout=30, allow_redirects=True)
    if r.status_code in (200, 206):
        cr = r.headers.get("Content-Range", "")
        if "/" in cr:
            return int(cr.split("/")[-1])
        return int(r.headers.get("Content-Length", 0))
    raise RuntimeError(f"HTTP {r.status_code}")

def dl():
    total = remote_size(URL)
    log(f"远程大小 {total/1048576:.1f}MB")
    attempt = 0
    while True:
        attempt += 1
        try:
            pos = os.path.getsize(DEST) if os.path.exists(DEST) else 0
            if pos == total:
                return True
            if pos > total:
                os.remove(DEST)
                pos = 0
            h = {**UA}
            if pos:
                h["Range"] = f"bytes={pos}-"
            with requests.get(URL, headers=h, stream=True, timeout=(30, 60), allow_redirects=True) as r:
                if r.status_code == 416:
                    return os.path.getsize(DEST) == total
                r.raise_for_status()
                mode = "ab" if pos and r.status_code == 206 else "wb"
                if mode == "wb":
                    pos = 0
                expect = int(r.headers.get("Content-Length", 0)) + pos
                with open(DEST, mode) as f:
                    for chunk in r.iter_content(1024 * 1024):
                        f.write(chunk)
                        pos += len(chunk)
            final = os.path.getsize(DEST)
            if final == total:
                log(f"DONE {final/1048576:.1f}MB 尝试{attempt}次")
                return True
            raise RuntimeError(f"不完整 {final}/{total}")
        except Exception as e:
            log(f"RETRY({attempt}) {type(e).__name__} {str(e)[:80]}")
            time.sleep(min(10 * attempt, 60))

dl()

log("解压中...")
with zipfile.ZipFile(DEST) as z:
    z.extractall(EXTRACT)
inner = os.path.join(EXTRACT, "ffmpeg-master-latest-win64-gpl")
if os.path.isdir(os.path.join(FINAL, "bin")):
    log("D:\\ffmpeg 已存在，跳过复制")
else:
    if os.path.isdir(FINAL):
        subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", FINAL])
    os.rename(inner, FINAL)
    log(f"已安装到 {FINAL}")

with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS) as k:
    cur, _ = winreg.QueryValueEx(k, "Path")
    bin_dir = r"D:\ffmpeg\bin"
    parts = [p for p in cur.split(";") if p.strip()]
    if bin_dir.lower() not in [p.lower() for p in parts]:
        winreg.SetValueEx(k, "Path", 0, winreg.REG_EXPAND_SZ, ";".join(parts + [bin_dir]))
        log(f"PATH 已添加 {bin_dir}")
    else:
        log("PATH 已包含 ffmpeg")

import ctypes
ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 0x0002, 5000, ctypes.byref(ctypes.c_ulong()))

r = subprocess.run([r"D:\ffmpeg\bin\ffmpeg.exe", "-version"], capture_output=True, text=True)
log(f"验证: {r.stdout.splitlines()[0] if r.stdout else r.stderr[:100]}")
print("OK" if r.returncode == 0 else "FAIL")

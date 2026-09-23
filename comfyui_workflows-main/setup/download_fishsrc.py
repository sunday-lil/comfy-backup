# -*- coding: utf-8 -*-
"""下载 fish-speech 源码包并解压到 D:\fish-speech-main（无 Content-Length 时用 gzip 校验）"""
import os, sys, time, gzip, tarfile, requests

URL = "https://ghfast.top/https://github.com/fishaudio/fish-speech/archive/refs/heads/main.tar.gz"
DEST = r"D:\fish-speech_dl\main.tar.gz"
EXTRACT_TO = "D:/"
LOG = r"D:\comfy\comfyui_workflows-main\setup\logs\fish_install.log"
UA = {"User-Agent": "Mozilla/5.0"}

def log(m):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {m}\n")
    print(m)

def remote_size():
    try:
        r = requests.get(URL, headers={**UA, "Range": "bytes=0-0"}, timeout=30, allow_redirects=True)
        if r.status_code in (200, 206):
            cr = r.headers.get("Content-Range", "")
            if "/" in cr and not cr.endswith("/*"):
                return int(cr.split("/")[-1])
            cl = r.headers.get("Content-Length")
            if cl:
                return int(cl)
    except Exception as e:
        log(f"探测大小失败: {e}")
    return 0

def gzip_ok(path):
    try:
        with gzip.open(path, "rb") as g:
            while g.read(8 * 1024 * 1024):
                pass
        return True
    except Exception:
        return False

def main():
    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    total = remote_size()
    log(f"远程大小: {total if total else '未知'}")
    attempt = 0
    while True:
        attempt += 1
        try:
            pos = os.path.getsize(DEST) if os.path.exists(DEST) else 0
            # 已完成判断
            if (total and pos == total) or (not total and pos and gzip_ok(DEST)):
                log(f"DONE {pos/1048576:.1f}MB 尝试{attempt}次")
                break
            if total and pos > total:
                os.remove(DEST)
                pos = 0
            h = {**UA}
            if pos:
                h["Range"] = f"bytes={pos}-"
            with requests.get(URL, headers=h, stream=True, timeout=(30, 60), allow_redirects=True) as r:
                if r.status_code == 416:
                    if gzip_ok(DEST):
                        log(f"DONE(416) {os.path.getsize(DEST)/1048576:.1f}MB")
                        return finish()
                    raise RuntimeError("416 但文件不完整")
                r.raise_for_status()
                mode = "ab" if pos and r.status_code == 206 else "wb"
                if mode == "wb":
                    pos = 0
                with open(DEST, mode) as f:
                    for chunk in r.iter_content(1024 * 1024):
                        f.write(chunk)
                        pos += len(chunk)
            # 流结束, 校验
            if total:
                if os.path.getsize(DEST) == total:
                    log(f"DONE {total/1048576:.1f}MB 尝试{attempt}次")
                    break
                raise RuntimeError(f"不完整 {os.path.getsize(DEST)}/{total}")
            else:
                if gzip_ok(DEST):
                    log(f"DONE(gzip验证) {os.path.getsize(DEST)/1048576:.1f}MB 尝试{attempt}次")
                    break
                raise RuntimeError("gzip 校验失败")
        except Exception as e:
            log(f"RETRY({attempt}) {type(e).__name__} {str(e)[:80]}")
            time.sleep(min(5 * attempt, 30))
    finish()

def finish():
    log("解压中...")
    with tarfile.open(DEST, "r:gz") as t:
        t.extractall(EXTRACT_TO)
    log("解压完成 -> D:\\fish-speech-main")
    print("OK")

if __name__ == "__main__":
    main()

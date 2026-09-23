# -*- coding: utf-8 -*-
"""下载 fish-speech v1.5.1 源码并解压覆盖到 D:\\fish-speech-main（保留 venv/checkpoints）"""
import os, tarfile, time, requests

SHA = "781bf1cd7afef831fc58928a6444a2161449dae5"  # 2025-10-20 "Finetune support of OpenAudio-S1" = S1-mini 时代最终代码
URL = f"https://ghfast.top/https://github.com/fishaudio/fish-speech/archive/{SHA}.tar.gz"
DEST = r"D:\fish-speech_dl\s1.tar.gz"
EXTRACT_TMP = r"D:\fish-speech_dl\s1_extract"
TARGET = "D:/fish-speech-main"
UA = {"User-Agent": "Mozilla/5.0"}

os.makedirs(os.path.dirname(DEST), exist_ok=True)

# 下载（带完整性回退）
for attempt in range(1, 6):
    try:
        pos = os.path.getsize(DEST) if os.path.exists(DEST) else 0
        h = dict(UA)
        if pos:
            h["Range"] = f"bytes={pos}-"
        with requests.get(URL, headers=h, stream=True, timeout=(30, 60)) as r:
            r.raise_for_status()
            mode = "ab" if pos and r.status_code == 206 else "wb"
            with open(DEST, mode) as f:
                for chunk in r.iter_content(1024 * 256):
                    f.write(chunk)
        # gzip 完整性校验
        import gzip
        with gzip.open(DEST, "rb") as gz:
            while gz.read(1024 * 1024):
                pass
        print(f"下载完成 {os.path.getsize(DEST)/1e6:.1f}MB 尝试{attempt}次")
        break
    except Exception as e:
        print(f"RETRY({attempt}): {type(e).__name__} {str(e)[:100]}")
        time.sleep(5 * attempt)
else:
    raise SystemExit("下载失败")

# 解压到临时目录
if os.path.exists(EXTRACT_TMP):
    import shutil
    shutil.rmtree(EXTRACT_TMP)
with tarfile.open(DEST, "r:gz") as t:
    t.extractall(EXTRACT_TMP)

src = None
for name in os.listdir(EXTRACT_TMP):
    if name.startswith("fish-speech-"):
        src = os.path.join(EXTRACT_TMP, name)
        break
assert src and os.path.isdir(src), os.listdir(EXTRACT_TMP)

# 覆盖复制（跳过 venv / checkpoints / .project-root 之外的已有杂项不动）
import shutil
skip_names = {"venv", "checkpoints"}
n = 0
for item in os.listdir(src):
    if item in skip_names:
        continue
    s = os.path.join(src, item)
    d = os.path.join(TARGET, item)
    if os.path.isdir(s):
        if os.path.isdir(d):
            shutil.rmtree(d)
        shutil.copytree(s, d)
    else:
        if os.path.exists(d):
            os.remove(d)
        shutil.copy2(s, d)
    n += 1
    print("覆盖:", item)
print(f"完成，共 {n} 项")

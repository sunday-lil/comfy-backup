# -*- coding: utf-8 -*-
"""用管线同款 payload 测试 Fish Speech /v1/tts"""
import requests, sys, time

API = "http://127.0.0.1:8080/v1/tts"
payload = {
    "text": "你好呀，我是你的配音小助手。今天天气真不错，我们一起去看看森林里的小白狐吧！",
    "chunk_length": 300,
    "format": "wav",
    "top_p": 0.8,
    "temperature": 0.8,
    "repetition_penalty": 1.1,
    "max_new_tokens": 1024,
    "normalize": True,
    "streaming": False,
}
t0 = time.time()
r = requests.post(API, json=payload, timeout=300)
dt = time.time() - t0
print(f"HTTP {r.status_code}, {len(r.content)} bytes, {dt:.1f}s, content-type={r.headers.get('content-type')}")
if r.status_code == 200 and len(r.content) > 1000:
    out = r"D:\comfy\comfyui_workflows-main\setup\logs\tts_test.wav"
    with open(out, "wb") as f:
        f.write(r.content)
    print("saved:", out)
else:
    print(r.text[:500])
    sys.exit(1)

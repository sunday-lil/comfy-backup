# -*- coding: utf-8 -*-
import requests, re

for u in [
    "https://github.com/fishaudio/fish-speech/tags.atom",
    "https://gh-proxy.com/https://github.com/fishaudio/fish-speech/tags.atom",
]:
    try:
        r = requests.get(u, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        tags = re.findall(r"/releases/tag/([^<]+)", r.text)
        print(u.split("/")[2], r.status_code, tags[:25])
        if tags:
            break
    except Exception as e:
        print("ERR", type(e).__name__, str(e)[:80])

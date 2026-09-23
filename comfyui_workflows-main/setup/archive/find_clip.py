# 在 Comfy-Org 各 repackaged 仓库中找 CLIP-ViT-H clip_vision 文件
import json, urllib.request

def api(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

repos = [
    "Comfy-Org/Wan_2.1_ComfyUI_Repackaged",
    "Comfy-Org/Wan2.2_ComfyUI_Repackaged",
]
for repo in repos:
    print(f"=== {repo} ===")
    try:
        d = api(f"https://modelscope.cn/api/v1/models/{repo}/repo/files?Recursive=true")
        for f in d["Data"]["Files"]:
            p = f["Path"]
            if f["Type"] != "tree" and "clip_vision" in p.lower() and p.endswith(".safetensors"):
                print(f"  {p}  {f['Size']/1048576:.0f}MB")
    except Exception as e:
        print("  FAIL:", e)

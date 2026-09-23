# 查询 ModelScope API：找 lightx2v LoRA 和 CLIP-ViT-H 的可用源
import json, urllib.request

def api(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

# 1. Kijai/WanVideo_comfy 找 lightx2v i2v lora
print("=== Kijai/WanVideo_comfy: lightx2v LoRA ===")
try:
    d = api("https://modelscope.cn/api/v1/models/Kijai/WanVideo_comfy/repo/files?Recursive=true")
    for f in d["Data"]["Files"]:
        p = f["Path"]
        if f["Type"] != "tree" and p.endswith(".safetensors") and "lightx2v" in p.lower() and "i2v" in p.lower():
            print(f"  {p}  {f['Size']/1048576:.0f}MB")
except Exception as e:
    print("  FAIL:", e)

# 2. 搜索 CLIP-ViT-H
print("=== 搜索 CLIP-ViT-H ===")
try:
    d = api("https://modelscope.cn/api/v1/dolphin/models?PageSize=10&PageNumber=1&Search=CLIP-ViT-H-14-laion2B-s32B-b79K")
    for m in d.get("Data", []):
        print(f"  {m.get('Path')}/{m.get('Name')}")
except Exception as e:
    print("  FAIL:", e)

# 3. 搜索 lightx2v Wan2.2 LoRA 搬运
print("=== 搜索 Wan2.2-Distill-Loras ===")
try:
    d = api("https://modelscope.cn/api/v1/dolphin/models?PageSize=10&PageNumber=1&Search=Wan2.2-Distill-Loras")
    for m in d.get("Data", []):
        print(f"  {m.get('Path')}/{m.get('Name')}")
except Exception as e:
    print("  FAIL:", e)

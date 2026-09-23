import requests
import time
import json

prompt_ids = [
    ("video_shot1", "03b6f19e-1f0b-4cfa-9af7-c7c48515eb61", "video/shot1"),
    ("video_shot2", "a141eadf-b77c-4746-a268-2e636bceb428", "video/shot2"),
    ("video_shot3", "be604f0c-8951-43db-94bc-49fdc3a9f3bd", "video/shot3"),
]

results = {}
start_time = time.time()

print("🎬 视频生成监控开始")
print("=" * 50)

while len(results) < len(prompt_ids):
    for name, pid, prefix in prompt_ids:
        if name in results:
            continue
        
        try:
            h = requests.get(f"http://127.0.0.1:8188/history/{pid}", timeout=10).json()
            if pid in h:
                s = h[pid].get("status", {})
                if s.get("completed"):
                    outs = h[pid].get("outputs", {})
                    for nid, out in outs.items():
                        if "videos" in out:
                            for v in out["videos"]:
                                results[name] = v["filename"]
                                elapsed = time.time() - start_time
                                print(f"✅ {name} 完成! ({elapsed/60:.1f}分钟)")
                                print(f"   📁 {prefix}/{v['filename']}")
                elif s.get("errored"):
                    results[name] = f"ERROR: {s.get('error')}"
                    print(f"❌ {name}: {s.get('error')}")
        except Exception as e:
            pass
    
    if len(results) < len(prompt_ids):
        elapsed = time.time() - start_time
        remaining = len(prompt_ids) - len(results)
        print(f"\r⏳ {elapsed/60:.1f}分钟 - 剩余{remaining}个视频 - {time.strftime('%H:%M:%S')}", end="")
        time.sleep(10)

print("\n" + "=" * 50)
print("🎉 全部完成!")
print("=" * 50)
for name, fname in results.items():
    print(f"  {name}: {fname}")

# 保存结果
with open("video_results.json", "w") as f:
    json.dump(results, f)
print("\n📁 结果已保存到 video_results.json")

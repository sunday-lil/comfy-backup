#!/usr/bin/env python3
"""视频生成监控 - 修复版"""
import requests
import time
import json
import sys

PROMPT_IDS = [
    ("shot1", "video/shot1"),
    ("shot2", "video/shot2"),
    ("shot3", "video/shot3"),
]

COMFYUI = "http://127.0.0.1:8188"

def check_done(pid):
    """检查单个prompt是否完成，返回(完成bool, 错误str或None, 输出路径或None)"""
    try:
        h = requests.get(f"{COMFYUI}/history/{pid}", timeout=10).json()
    except Exception as e:
        return False, None, None
    
    if pid not in h:
        return False, None, None
    
    status = h[pid].get("status", {})
    # ComfyUI status 可能有 completed 或 state 字段
    if status.get("errored"):
        return True, status.get("error", "unknown error"), None
    
    # 检查是否有输出
    outputs = h[pid].get("outputs", {})
    for nid, out in outputs.items():
        if "videos" in out and out["videos"]:
            return True, None, out["videos"][0]["filename"]
        if "images" in out and out["images"]:
            # 视频也可能放在 images 里
            return True, None, out["images"][0]["filename"]
    
    return False, None, None


def main():
    if len(sys.argv) < 4:
        print("用法: python monitor.py <prompt_id_1> <prefix_1> [<prompt_id_2> <prefix_2> ...]")
        sys.exit(1)
    
    # 解析参数: pid1 prefix1 pid2 prefix2 ...
    args = sys.argv[1:]
    tasks = []
    for i in range(0, len(args), 2):
        tasks.append((args[i], args[i+1]))
    
    results = {}
    start = time.time()
    completed_count = 0
    
    print(f"🎬 监控 {len(tasks)} 个任务")
    print("=" * 50)
    
    while completed_count < len(tasks):
        completed_count = 0
        still_running = []
        
        for name, pid in tasks:
            if name in results:
                completed_count += 1
                continue
                
            done, err, fname = check_done(pid)
            
            if done:
                if err:
                    results[name] = f"ERROR: {err}"
                    print(f"❌ {name}: {err}")
                else:
                    results[name] = fname
                    elapsed = time.time() - start
                    print(f"✅ {name} 完成 ({elapsed/60:.1f}分钟) → {fname}")
                completed_count += 1
            else:
                still_running.append(name)
        
        if completed_count < len(tasks):
            elapsed = time.time() - start
            print(f"\r⏳ {elapsed/60:.1f}分钟 - 剩余{len(tasks)-completed_count}个: {', '.join(still_running)}   ", end="", flush=True)
            time.sleep(10)
    
    print("\n" + "=" * 50)
    print("🎉 全部完成!")
    for name, fname in results.items():
        print(f"  {name}: {fname}")
    
    with open("video_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n📁 结果已保存到 video_results.json")


if __name__ == "__main__":
    main()

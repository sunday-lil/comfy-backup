# -*- coding: utf-8 -*-
"""模型统一下载器：断点续传 + 无限重试 + 完成后重命名对齐 workflow 文件名"""
import os, time, threading, requests

BASE = r"D:\comfy\ComfyUI_windows_portable\ComfyUI\models"
LOG = r"D:\comfy\comfyui_workflows-main\setup\logs\downloader.log"
UA = {"User-Agent": "Mozilla/5.0"}

ZI = "https://modelscope.cn/models/Comfy-Org/z_image_turbo/resolve/master/split_files"
WAN21 = "https://modelscope.cn/models/Comfy-Org/Wan_2.1_ComfyUI_Repackaged/resolve/master/split_files"
WAN22 = "https://modelscope.cn/models/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/master/split_files"
KIJAI = "https://modelscope.cn/models/Kijai/WanVideo_comfy/resolve/master"

# (url, 最终路径)  文件名与 workflow JSON 期望完全一致
GROUP_T2I = [
    (f"{ZI}/vae/ae.safetensors", f"{BASE}\\vae\\ae.safetensors"),
    (f"{ZI}/diffusion_models/z_image_turbo_bf16.safetensors", f"{BASE}\\diffusion_models\\z_image_turbo_bf16.safetensors"),
    (f"{ZI}/text_encoders/qwen_3_4b.safetensors", f"{BASE}\\text_encoders\\qwen_3_4b.safetensors"),
]
GROUP_I2V = [
    (f"{WAN22}/vae/wan_2.1_vae.safetensors", f"{BASE}\\vae\\wan_2.1_vae.safetensors"),
    (f"{KIJAI}/LoRAs/Wan22_Lightx2v/Wan_2_2_I2V_A14B_HIGH_lightx2v_4step_lora_260412_rank_64_fp16.safetensors",
     f"{BASE}\\loras\\wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"),
    (f"{KIJAI}/LoRAs/Wan22_Lightx2v/Wan_2_2_I2V_A14B_LOW_lightx2v_4step_lora_260412_rank_64_fp16.safetensors",
     f"{BASE}\\loras\\wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors"),
    (f"{WAN21}/clip_vision/clip_vision_h.safetensors",
     f"{BASE}\\clip_vision\\CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"),
    (f"{WAN22}/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", f"{BASE}\\text_encoders\\umt5_xxl_fp8_e4m3fn_scaled.safetensors"),
    (f"{WAN22}/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", f"{BASE}\\diffusion_models\\wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"),
    (f"{WAN22}/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors", f"{BASE}\\diffusion_models\\wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"),
]
COMFYUI_7Z = ("https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia.7z",
              r"D:\comfy\ComfyUI_windows_portable_nvidia.7z")

os.makedirs(os.path.dirname(LOG), exist_ok=True)
_lock = threading.Lock()

def log(msg):
    with _lock:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")

def remote_size(url):
    """用 Range:0-0 拿真实总大小（Content-Range: bytes 0-0/TOTAL）"""
    r = requests.get(url, headers={**UA, "Range": "bytes=0-0"}, timeout=30, allow_redirects=True)
    if r.status_code in (200, 206):
        cr = r.headers.get("Content-Range", "")
        if "/" in cr:
            return int(cr.split("/")[-1])
        return int(r.headers.get("Content-Length", 0))
    raise RuntimeError(f"HTTP {r.status_code}")

def download(url, dest):
    name = os.path.basename(dest)
    if os.path.exists(dest):
        local = os.path.getsize(dest)
        try:
            total = remote_size(url)
        except Exception:
            total = 0
        if total and local == total:
            log(f"SKIP {name} 已完成 {local/1073741824:.2f}GB")
            return True
    attempt = 0
    while True:
        attempt += 1
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            pos = os.path.getsize(dest) if os.path.exists(dest) else 0
            headers = {**UA}
            if pos:
                headers["Range"] = f"bytes={pos}-"
            with requests.get(url, headers=headers, stream=True, timeout=(30, 60), allow_redirects=True) as r:
                if r.status_code == 416:  # 已下载完
                    log(f"DONE {name} (416=完整)")
                    return True
                r.raise_for_status()
                mode = "ab" if pos and r.status_code == 206 else "wb"
                if mode == "wb":
                    pos = 0
                total = int(r.headers.get("Content-Length", 0)) + pos
                last_log = time.time()
                with open(dest, mode) as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)
                        pos += len(chunk)
                        if time.time() - last_log > 30:
                            pct = f"{pos/total*100:.1f}%" if total else "?"
                            log(f"... {name} {pos/1073741824:.2f}GB / {total/1073741824:.2f}GB ({pct})")
                            last_log = time.time()
            # 校验（大小必须精确一致：既不能少也不能多）
            final = os.path.getsize(dest)
            if total and final != total:
                if final > total:  # 多余字节：截断后重查
                    with open(dest, "r+b") as f:
                        f.truncate(total)
                    final = os.path.getsize(dest)
                    log(f"TRUNC {name} 截断到 {total/1073741824:.2f}GB")
                if final < total:
                    raise RuntimeError(f"不完整 {final}/{total}")
            log(f"DONE {name} {final/1073741824:.2f}GB 尝试{attempt}次")
            return True
        except Exception as e:
            log(f"RETRY({attempt}) {name}: {type(e).__name__} {str(e)[:100]}")
            time.sleep(min(10 * attempt, 60))

def worker(tag, files):
    for url, dest in files:
        log(f"START [{tag}] {os.path.basename(dest)}")
        download(url, dest)
    log(f"GROUP_DONE [{tag}]")

threads = [
    threading.Thread(target=worker, args=("t2i", GROUP_T2I), daemon=True),
    threading.Thread(target=worker, args=("i2v", GROUP_I2V), daemon=True),
    threading.Thread(target=worker, args=("comfyui", [COMFYUI_7Z]), daemon=True),
]
log("===== 下载器启动 =====")
for t in threads:
    t.start()
for t in threads:
    t.join()
log("===== 全部下载完成 =====")

# 用 range GET 实际下载 1MB 验证所有模型 URL 可用性
import urllib.request, sys

urls = {
    "ae.safetensors": "https://modelscope.cn/models/Comfy-Org/z_image_turbo/resolve/master/split_files/vae/ae.safetensors",
    "z_image_turbo_bf16": "https://modelscope.cn/models/Comfy-Org/z_image_turbo/resolve/master/split_files/diffusion_models/z_image_turbo_bf16.safetensors",
    "qwen_3_4b": "https://modelscope.cn/models/Comfy-Org/z_image_turbo/resolve/master/split_files/text_encoders/qwen_3_4b.safetensors",
    "wan_2.1_vae": "https://modelscope.cn/models/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/master/split_files/vae/wan_2.1_vae.safetensors",
    "umt5_xxl_fp8": "https://modelscope.cn/models/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/master/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
    "wan22_high_fp8": "https://modelscope.cn/models/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/master/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
    "wan22_low_fp8": "https://modelscope.cn/models/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/master/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
    "clip_vision_H": "https://modelscope.cn/models/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/master/split_files/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
    # lightx2v LoRA 备选源
    "lora_high_hfmirror": "https://hf-mirror.com/lightx2v/Wan2.2-Lightning/resolve/main/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
    "lora_low_hfmirror": "https://hf-mirror.com/lightx2v/Wan2.2-Lightning/resolve/main/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
}

for name, url in urls.items():
    try:
        req = urllib.request.Request(url, headers={"Range": "bytes=0-1048575", "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read(65536)  # 只读 64KB 足够判断
            print(f"{name}: HTTP {r.status} 首块 {len(data)} 字节 -> {'OK' if len(data) > 1024 else 'EMPTY!'}")
    except Exception as e:
        print(f"{name}: FAIL {e}")

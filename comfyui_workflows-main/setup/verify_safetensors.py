# -*- coding: utf-8 -*-
"""校验 safetensors 文件结构完整性: 8字节头长度 + JSON头 + 张量数据 == 文件大小"""
import sys, json, struct

def check(path):
    size = __import__("os").path.getsize(path)
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        if n > size - 8:
            print(f"[FAIL] {path}: 头部长度 {n} 超出文件")
            return False
        hdr = json.loads(f.read(n))
        data_begin = 8 + n
        end = 0
        for k, v in hdr.items():
            if k == "__metadata__":
                continue
            end = max(end, v["data_offsets"][1])
        ok = data_begin + end == size
        print(f"[{'OK' if ok else 'FAIL'}] {path.split(chr(92))[-1]}: "
              f"文件={size/1073741824:.2f}GB 头JSON={n/1048576:.1f}MB "
              f"张量={len([k for k in hdr if k != '__metadata__'])}个 "
              f"数据区末尾={data_begin+end} 预期文件大小={size} 差={size-(data_begin+end)}")
        return ok

if __name__ == "__main__":
    files = [
        r"D:\comfy\ComfyUI_windows_portable\ComfyUI\models\diffusion_models\z_image_turbo_bf16.safetensors",
        r"D:\comfy\ComfyUI_windows_portable\ComfyUI\models\text_encoders\qwen_3_4b.safetensors",
        r"D:\comfy\ComfyUI_windows_portable\ComfyUI\models\vae\ae.safetensors",
        r"D:\comfy\ComfyUI_windows_portable\ComfyUI\models\diffusion_models\wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
        r"D:\comfy\ComfyUI_windows_portable\ComfyUI\models\diffusion_models\wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
        r"D:\comfy\ComfyUI_windows_portable\ComfyUI\models\text_encoders\umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        r"D:\comfy\ComfyUI_windows_portable\ComfyUI\models\vae\wan_2.1_vae.safetensors",
        r"D:\comfy\ComfyUI_windows_portable\ComfyUI\models\clip_vision\CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
        r"D:\comfy\ComfyUI_windows_portable\ComfyUI\models\loras\wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
        r"D:\comfy\ComfyUI_windows_portable\ComfyUI\models\loras\wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
    ]
    bad = [f for f in files if not check(f)]
    print(f"\n{'全部通过' if not bad else f'{len(bad)} 个文件损坏'}")
    sys.exit(1 if bad else 0)

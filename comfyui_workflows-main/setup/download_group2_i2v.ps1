# 图生视频模型下载（组2：Wan2.2 14B fp8 + 配套）
# 用法: powershell -File download_group2_i2v.ps1
$ErrorActionPreference = "Continue"
$base = "D:\comfy\ComfyUI_windows_portable\ComfyUI\models"
$log = "D:\comfy\comfyui_workflows-main\setup\logs\group2_i2v.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

$wan = "https://modelscope.cn/models/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/master/split_files"
$lx2v = "https://modelscope.cn/models/lightx2v/Wan2.2-Lightning/resolve/master"

$files = @(
    @{ url = "$wan/vae/wan_2.1_vae.safetensors";                                dest = "$base\vae\wan_2.1_vae.safetensors" },
    @{ url = "$lx2v/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"; dest = "$base\loras\wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors" },
    @{ url = "$lx2v/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors";  dest = "$base\loras\wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors" },
    @{ url = "$wan/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors";    dest = "$base\clip_vision\CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors" },
    @{ url = "$wan/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors";       dest = "$base\text_encoders\umt5_xxl_fp8_e4m3fn_scaled.safetensors" },
    @{ url = "$wan/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"; dest = "$base\diffusion_models\wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors" },
    @{ url = "$wan/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors";  dest = "$base\diffusion_models\wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors" }
)

foreach ($f in $files) {
    $name = Split-Path $f.dest -Leaf
    Add-Content $log "[$(Get-Date -Format 'HH:mm:ss')] START $name"
    for ($i = 1; $i -le 10; $i++) {
        curl.exe -sS -L -C - --retry 3 --retry-delay 5 --connect-timeout 30 -o $f.dest $f.url 2>>$log
        if ($LASTEXITCODE -eq 0) { break }
        Add-Content $log "[$(Get-Date -Format 'HH:mm:ss')] RETRY($i) $name exit=$LASTEXITCODE"
        Start-Sleep 5
    }
    $size = if (Test-Path $f.dest) { [math]::Round((Get-Item $f.dest).Length/1GB, 2) } else { 0 }
    Add-Content $log "[$(Get-Date -Format 'HH:mm:ss')] DONE  $name ${size}GB exit=$LASTEXITCODE"
}
Add-Content $log "[$(Get-Date -Format 'HH:mm:ss')] GROUP2_ALL_DONE"

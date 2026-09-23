# 文生图模型下载（组1：z-image-turbo 全家桶，优先级最高）
# 用法: powershell -File download_group1_t2i.ps1
$ErrorActionPreference = "Continue"
$base = "D:\comfy\ComfyUI_windows_portable\ComfyUI\models"
$log = "D:\comfy\comfyui_workflows-main\setup\logs\group1_t2i.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

$files = @(
    @{ url = "https://modelscope.cn/models/Comfy-Org/z_image_turbo/resolve/master/split_files/vae/ae.safetensors";                          dest = "$base\vae\ae.safetensors" },
    @{ url = "https://modelscope.cn/models/Comfy-Org/z_image_turbo/resolve/master/split_files/diffusion_models/z_image_turbo_bf16.safetensors"; dest = "$base\diffusion_models\z_image_turbo_bf16.safetensors" },
    @{ url = "https://modelscope.cn/models/Comfy-Org/z_image_turbo/resolve/master/split_files/text_encoders/qwen_3_4b.safetensors";           dest = "$base\text_encoders\qwen_3_4b.safetensors" }
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
Add-Content $log "[$(Get-Date -Format 'HH:mm:ss')] GROUP1_ALL_DONE"

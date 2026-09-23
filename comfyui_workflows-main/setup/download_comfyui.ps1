# ComfyUI 便携版下载（GitHub release，支持断点续传）
$log = "D:\comfy\comfyui_workflows-main\setup\logs\comfyui_dl.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
for ($i = 1; $i -le 20; $i++) {
    curl.exe -sS -L -C - --retry 3 --retry-delay 5 --connect-timeout 30 -o D:\comfy\ComfyUI_windows_portable_nvidia.7z https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia.7z 2>>$log
    if ($LASTEXITCODE -eq 0) { break }
    Add-Content $log "[$(Get-Date -Format 'HH:mm:ss')] RETRY($i) exit=$LASTEXITCODE"
    Start-Sleep 10
}
$size = [math]::Round((Get-Item D:\comfy\ComfyUI_windows_portable_nvidia.7z -ErrorAction SilentlyContinue).Length/1MB, 1)
Add-Content $log "[$(Get-Date -Format 'HH:mm:ss')] FINAL exit=$LASTEXITCODE size=${size}MB"

@echo off
chcp 65001 >nul
title 短视频流水线环境

REM 确保 ffmpeg 可用（兜底：即使 PATH 未刷新也能找到）
if exist D:\ffmpeg\bin set PATH=%PATH%;D:\ffmpeg\bin

REM 检查 ComfyUI 是否已运行
curl -s -o nul -m 3 http://127.0.0.1:8188/system_stats
if %errorlevel%==0 (
    echo [OK] ComfyUI 已在运行
    goto ready
)

echo [启动] ComfyUI 服务（RTX 5060）...
start "ComfyUI" /min "D:\comfy\ComfyUI_windows_portable\python_embeded\python.exe" -s "D:\comfy\ComfyUI_windows_portable\ComfyUI\main.py" --port 8188

echo 等待 ComfyUI 就绪（最多60秒）...
set /a n=0
:waitloop
timeout /t 5 /nobreak >nul
curl -s -o nul -m 3 http://127.0.0.1:8188/system_stats
if %errorlevel%==0 goto ready
set /a n+=5
if %n% lss 60 goto waitloop
echo [警告] ComfyUI 60秒内未就绪，请检查 D:\comfy\ComfyUI_windows_portable 是否正常
goto ready

:ready
echo.
echo ============================================
echo   环境就绪！常用命令：
echo.
echo   图形界面（推荐，一键全套）:
echo     双击上级目录的 总启动.bat  （或 py gui.py）
echo   交互模式（推荐）:
echo     py main_pipeline.py --interactive
echo.
echo   一键生成（含配音）:
echo     py main_pipeline.py -d "一个小男孩在森林里遇到一只白狐" -t "配音文本"
echo.
echo   仅生成定妆照:
echo     py main_pipeline.py -d "描述" --costume-only
echo.
echo   网页界面:
echo     py web_ui\app.py   然后访问 http://127.0.0.1:5001
echo.
echo   说明: TTS(Fish Speech) 由管线在配音阶段
echo   自动启动/停止，无需手动运行（8GB 显存
echo   与 ComfyUI 视频生成分时复用）
echo ============================================
echo.
cd /d d:\comfy\comfyui_workflows-main
cmd /k

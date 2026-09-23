@echo off
chcp 65001 >nul
title 短视频制作器 - 总启动

REM ffmpeg 兜底（即使 PATH 未刷新也能找到）
if exist D:\ffmpeg\bin set PATH=%PATH%;D:\ffmpeg\bin

REM 进入流水线项目目录（本脚本在 d:\comfy 根目录，项目在子目录）
cd /d "%~dp0comfyui_workflows-main"

echo ============================================
echo   总启动：图形界面 + 全套环境
echo.
echo   gui.py 会自动完成：
echo     - ComfyUI   未运行则自动启动（约1分钟）
echo     - Ollama    未运行则自动启动
echo     - Fish Speech 配音阶段按需启动/停止
echo ============================================
echo.

py gui.py

REM 异常退出时保留窗口方便看错误
if errorlevel 1 pause

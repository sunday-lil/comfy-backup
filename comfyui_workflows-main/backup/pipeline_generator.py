#!/usr/bin/env python3
"""
短视频生成流水线 - 一键执行
文生图 → 图生视频 → TTS → 音视频合并

用法:
    python pipeline_generator.py --prompt "描述" --tts_text "配音文本" [--image-only] [--video-only]
"""

import argparse
import json
import os
import sys
import time
import requests
import subprocess
from pathlib import Path

# ============ 配置区 ============
COMFYUI_URL = "http://127.0.0.1:8188"
FISH_SPEECH_API = "http://localhost:8080/v1/tts"
OUTPUT_DIR = Path("output")
WORKFLOW_DIR = Path(__file__).parent

# 工作流模板路径
TXT2IMG_WORKFLOW = WORKFLOW_DIR / "文生图.json"
I2V_WORKFLOW = WORKFLOW_DIR / "wan2.2图文生视频.json"


def setup_output_dir():
    """创建输出目录"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "images").mkdir(exist_ok=True)
    (OUTPUT_DIR / "videos").mkdir(exist_ok=True)
    (OUTPUT_DIR / "audio").mkdir(exist_ok=True)
    print(f"📁 输出目录: {OUTPUT_DIR.absolute()}")


def check_comfyui_running():
    """检查 ComfyUI 是否运行"""
    try:
        response = requests.get(f"{COMFYUI_URL}/system_stats", timeout=5)
        return response.status_code == 200
    except:
        return False


def check_fish_speech_running():
    """检查 Fish Speech API 是否运行"""
    try:
        response = requests.get(f"{FISH_SPEECH_API.replace('/v1/tts', '/v1/health')}", timeout=5)
        return response.status_code == 200
    except:
        return False


def run_comfyui_workflow(workflow_path: str, filename_prefix: str = "pipeline") -> str:
    """
    运行 ComfyUI 工作流
    
    Returns:
        生成的图像/视频路径
    """
    if not os.path.exists(workflow_path):
        raise FileNotFoundError(f"工作流文件不存在: {workflow_path}")
    
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = json.load(f)
    
    # 修改 filename_prefix
    for node_id in workflow:
        if "SaveImage" in workflow[node_id].get("class_type", ""):
            workflow[node_id]["inputs"]["filename_prefix"] = filename_prefix
        if "SaveVideo" in workflow[node_id].get("class_type", ""):
            workflow[node_id]["inputs"]["filename_prefix"] = filename_prefix
    
    print(f"🚀 提交工作流: {workflow_path}")
    
    # 提交工作流
    response = requests.post(
        f"{COMFYUI_URL}/prompt",
        json={"prompt": workflow},
        timeout=30
    )
    
    if response.status_code != 200:
        raise RuntimeError(f"工作流提交失败: {response.status_code} - {response.text}")
    
    result = response.json()
    prompt_id = result.get("prompt_id")
    print(f"📋 Prompt ID: {prompt_id}")
    
    # 轮询等待完成
    print("⏳ 等待生成完成...")
    while True:
        time.sleep(3)
        status_response = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10)
        status_data = status_response.json()
        
        if prompt_id in status_data:
            status = status_data[prompt_id].get("status", {})
            if status.get("completed", False):
                print("✅ 生成完成!")
                # 获取输出文件路径
                outputs = status_data[prompt_id].get("outputs", {})
                for node_id, output in outputs.items():
                    if "images" in output:
                        return output["images"][0]["filename"]
                return None
            elif status.get("errored", False):
                raise RuntimeError(f"工作流执行出错: {status.get('error')}")
        
        print("  ...处理中")


def synthesize_tts(text: str, output_path: str) -> str:
    """调用 Fish Speech 合成语音"""
    print(f"🎤 正在合成语音: {text[:50]}{'...' if len(text) > 50 else ''}")
    
    payload = {
        "text": text,
        "chunk_length": 300,
        "format": "wav",
        "top_p": 0.8,
        "temperature": 0.8,
        "repetition_penalty": 1.1,
        "max_new_tokens": 1024,
        "normalize": True,
        "streaming": False,
    }
    
    response = requests.post(FISH_SPEECH_API, json=payload, timeout=300)
    
    if response.status_code != 200:
        raise RuntimeError(f"TTS 失败: {response.status_code} - {response.text}")
    
    with open(output_path, "wb") as f:
        f.write(response.content)
    
    size = os.path.getsize(output_path)
    print(f"✅ 音频已保存: {output_path} ({size/1024:.1f} KB)")
    return output_path


def merge_video_audio(video_path: str, audio_path: str, output_path: str):
    """使用 FFmpeg 合并视频和音频"""
    print(f"🎬 正在合并音视频...")
    
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-map", "0:v:0", "-map", "1:a:0",
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 失败: {result.stderr}")
    
    size = os.path.getsize(output_path)
    print(f"✅ 视频已保存: {output_path} ({size/1024/1024:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description="短视频生成流水线")
    parser.add_argument("--prompt", "-p", required=True, help="图像生成提示词")
    parser.add_argument("--tts-text", "-t", required=True, help="TTS 配音文本")
    parser.add_argument("--image-only", action="store_true", help="仅生成图像")
    parser.add_argument("--video-only", action="store_true", help="仅生成视频（需要已有图像）")
    parser.add_argument("--video-prompt", help="图生视频提示词（可选）")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🎬 短视频生成流水线")
    print("=" * 60)
    
    # 创建输出目录
    setup_output_dir()
    
    # 检查服务状态
    print("\n🔍 检查服务状态...")
    comfyui_ok = check_comfyui_running()
    fish_ok = check_fish_speech_running()
    
    print(f"   ComfyUI:     {'✅ 运行中' if comfyui_ok else '❌ 未运行'}")
    print(f"   Fish Speech: {'✅ 运行中' if fish_ok else '❌ 未运行'}")
    
    if not comfyui_ok:
        print("\n❌ 请先启动 ComfyUI（http://127.0.0.1:8188 未响应），Windows 下通常为: cd ComfyUI目录 && py main.py")
        sys.exit(1)
    
    if not args.image_only and not fish_ok:
        print("\n❌ 请先启动 Fish Speech API Server")
        sys.exit(1)
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    results = {}
    
    # Step 1: 文生图
    if not args.video_only:
        print(f"\n{'='*60}")
        print("📸 Step 1: 文生图")
        print(f"{'='*60}")
        
        image_file = run_comfyui_workflow(
            str(TXT2IMG_WORKFLOW),
            f"images/t2i_{timestamp}"
        )
        results["image"] = str(OUTPUT_DIR / "images" / image_file)
        print(f"   输出: {results['image']}")
    else:
        # 查找最新的图像
        images_dir = OUTPUT_DIR / "images"
        images = sorted(images_dir.glob("t2i_*.png"), key=os.path.getmtime)
        if not images:
            print("❌ 未找到已有图像，请先运行文生图")
            sys.exit(1)
        results["image"] = str(images[-1])
        print(f"   使用已有图像: {results['image']}")
    
    # Step 2: 图生视频
    if not args.image_only:
        print(f"\n{'='*60}")
        print("🎬 Step 2: 图生视频")
        print(f"{'='*60}")
        
        # 更新工作流中的图像路径
        video_file = run_comfyui_workflow(
            str(I2V_WORKFLOW),
            f"videos/i2v_{timestamp}"
        )
        results["video"] = str(OUTPUT_DIR / "videos" / video_file)
        print(f"   输出: {results['video']}")
        
        # Step 3: TTS
        print(f"\n{'='*60}")
        print("🎤 Step 3: TTS 语音合成")
        print(f"{'='*60}")
        
        audio_path = OUTPUT_DIR / "audio" / f"tts_{timestamp}.wav"
        synthesize_tts(args.tts_text, str(audio_path))
        results["audio"] = str(audio_path)
        
        # Step 4: 音视频合并
        print(f"\n{'='*60}")
        print("🔧 Step 4: 音视频合并")
        print(f"{'='*60}")
        
        final_path = OUTPUT_DIR / f"final_{timestamp}.mp4"
        merge_video_audio(
            results["video"],
            results["audio"],
            str(final_path)
        )
        results["final"] = str(final_path)
    
    # 完成
    print(f"\n{'='*60}")
    print("🎉 流水线执行完成!")
    print(f"{'='*60}")
    print("\n📁 输出文件:")
    for key, path in results.items():
        print(f"   {key}: {path}")


if __name__ == "__main__":
    main()

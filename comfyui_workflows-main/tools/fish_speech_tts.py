#!/usr/bin/env python3
"""
Fish Speech TTS 合成脚本
用法: python fish_speech_tts.py "要合成的文本" [输出文件名]
"""

import requests
import sys
import os
from pathlib import Path

# ============ 配置区 ============
API_URL = "http://localhost:8080/v1/tts"
DEFAULT_OUTPUT = "output/tts_output.wav"

def synthesize(text: str, output_path: str = None, reference_audio: str = None) -> str:
    """
    调用 Fish Speech API 合成语音
    
    Args:
        text: 要合成的文本
        output_path: 输出文件路径
        reference_audio: 参考音频路径（可选，用于声音克隆）
    
    Returns:
        生成的音频文件路径
    """
    if not text:
        raise ValueError("文本不能为空")
    
    if output_path is None:
        output_path = DEFAULT_OUTPUT
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    
    # 构建请求
    payload = {
        "text": text,
        "chunk_length": 300,           # 100-1000, 通常 200-300
        "format": "wav",               # wav/pcm/mp3/opus
        "top_p": 0.8,
        "temperature": 0.8,
        "repetition_penalty": 1.1,
        "max_new_tokens": 1024,
        "normalize": True,
        "streaming": False,
    }
    
    # 如果有参考音频，添加参考ID或参考音频
    if reference_audio and os.path.exists(reference_audio):
        # 通过参考音频克隆声音（需要先上传获取 reference_id）
        # 这里简化处理，假设 reference_audio 是路径
        payload["reference_audio"] = reference_audio
    
    print(f"🎤 正在合成: {text[:50]}{'...' if len(text) > 50 else ''}")
    print(f"📡 API: {API_URL}")
    
    try:
        response = requests.post(API_URL, json=payload, timeout=300)
        
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(response.content)
            size = os.path.getsize(output_path)
            print(f"✅ 音频已保存: {output_path} ({size/1024:.1f} KB)")
            return output_path
        else:
            print(f"❌ 错误 {response.status_code}: {response.text}")
            sys.exit(1)
            
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到 Fish Speech API")
        print("💡 请确保已启动 API Server:")
        print("   cd fish-speech目录")
        print("   py tools/api_server.py \\")
        print("     --llama-checkpoint-path .../checkpoints/FishAudio/s2-pro \\")
        print("     --decoder-checkpoint-path .../checkpoints/FishAudio/s2-pro/codec.pth \\")
        print("     --device cuda")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("❌ 请求超时（5分钟），文本可能太长")
        sys.exit(1)


def check_api_health():
    """检查 API 服务是否可用"""
    try:
        response = requests.get("http://localhost:8080/v1/health", timeout=5)
        if response.status_code == 200:
            print("✅ Fish Speech API 服务正常")
            return True
    except:
        pass
    print("⚠️ Fish Speech API 服务未运行，请先启动 API Server")
    return False


if __name__ == "__main__":
    # 命令行用法
    if len(sys.argv) < 2:
        print("Fish Speech TTS 合成工具")
        print("=" * 40)
        print("用法:")
        print("  python fish_speech_tts.py \"要合成的文本\" [输出文件]")
        print()
        print("示例:")
        print("  python fish_speech_tts.py \"你好世界\"")
        print("  python fish_speech_tts.py \"你好世界\" output/hello.wav")
        print()
        
        # 健康检查
        check_api_health()
        sys.exit(0)
    
    text = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT
    
    synthesize(text, output)

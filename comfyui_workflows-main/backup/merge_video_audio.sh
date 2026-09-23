#!/bin/bash
#===============================================================================
# 音视频合并脚本 - FFmpeg
# 用法: ./merge_video_audio.sh <视频文件> <音频文件> [输出文件]
#===============================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 默认值
VIDEO_FILE=""
AUDIO_FILE=""
OUTPUT_FILE="output/final_video.mp4"

# 帮助信息
show_help() {
    cat << EOF
音视频合并脚本

用法: $0 <视频文件> <音频文件> [输出文件]

参数:
  视频文件    输入视频路径 (mp4/avi/mov 等)
  音频文件    输入音频路径 (mp3/wav/m4a 等)
  输出文件    输出文件路径 (默认: output/final_video.mp4)

示例:
  $0 input/video.mp4 input/audio.wav
  $0 video.mp4 audio.mp3 my_output.mp4

注意:
  - 如果视频自带音频，会被替换
  - 输出格式目前固定为 H.264 视频 + AAC 音频的 MP4
EOF
}

# 检查参数
if [[ $# -lt 2 ]]; then
    show_help
    exit 1
fi

VIDEO_FILE="$1"
AUDIO_FILE="$2"
OUTPUT_FILE="${3:-$OUTPUT_FILE}"

# 检查文件是否存在
if [[ ! -f "$VIDEO_FILE" ]]; then
    echo -e "${RED}❌ 错误: 视频文件不存在: $VIDEO_FILE${NC}"
    exit 1
fi

if [[ ! -f "$AUDIO_FILE" ]]; then
    echo -e "${RED}❌ 错误: 音频文件不存在: $AUDIO_FILE${NC}"
    exit 1
fi

# 确保输出目录存在
mkdir -p "$(dirname "$OUTPUT_FILE")"

# 获取视频和音频信息
echo -e "${GREEN}📹 视频: $VIDEO_FILE${NC}"
VIDEO_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VIDEO_FILE" 2>/dev/null || echo "unknown")
VIDEO_SIZE=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$AUDIO_FILE" 2>/dev/null || echo "unknown")
echo -e "${GREEN}🎵 音频: $AUDIO_FILE${NC}"
echo -e "${GREEN}📁 输出: $OUTPUT_FILE${NC}"

# 执行合并
echo -e "${YELLOW}⚙️  正在合并...${NC}"

# 使用 FFmpeg 合并，忽略视频原有的音频
ffmpeg -y \
    -i "$VIDEO_FILE" \
    -i "$AUDIO_FILE" \
    -c:v libx264 -preset medium -crf 23 \
    -c:a aac -b:a 192k \
    -shortest \
    -map 0:v:0 -map 1:a:0 \
    "$OUTPUT_FILE" 2>&1

# 检查结果
if [[ -f "$OUTPUT_FILE" ]]; then
    SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo ""
    echo -e "${GREEN}✅ 合并完成!${NC}"
    echo -e "   文件: $OUTPUT_FILE"
    echo -e "   大小: $SIZE"
else
    echo -e "${RED}❌ 合并失败${NC}"
    exit 1
fi

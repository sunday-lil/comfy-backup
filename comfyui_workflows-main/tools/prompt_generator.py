#!/usr/bin/env python3
"""
提示词生成器 - 从场景描述自动生成文生图+图生视频提示词

用法:
    python prompt_generator.py
    # 交互式输入

    python prompt_generator.py "一个小男孩在教室里学编程"
    # 命令行模式
"""

import sys

# ============ 常用词汇库 ============

SUBJECT_VERBS = {
    "小男孩": ["坐着", "站着", "转头看向", "抬手", "指向", "点头", "摇头", "微笑", "大笑", "皱眉", "眨眼"],
    "小女孩": ["坐着", "站着", "转头看向", "抬手", "指向", "点头", "摇头", "微笑", "大笑", "皱眉", "眨眼"],
    "老师": ["转身", "抬手", "指向黑板", "点头", "微笑", "转头", "写字", "翻书"],
    "小男孩小女孩": ["对视", "一起看", "牵手", "挥手", "并肩坐"],
}

CAMERA_MOVEMENTS = [
    "镜头缓慢推近",
    "镜头轻微拉远",
    "镜头跟随主体移动",
    "镜头从左向右平移",
    "镜头从右向左平移",
    "镜头缓慢环绕",
    "镜头固定",
    "镜头轻微摇镜",
]

MOOD_TEMPOS = [
    "动作轻柔缓慢",
    "动作自然流畅",
    "动作轻快活泼",
    "动作舒缓放松",
    "动作充满活力",
]

# ============ 提示词生成函数 ============

def generate_image_prompt(theme: str, subject: str = None, style: str = "摄影风格") -> str:
    """生成文生图提示词"""
    
    base = f"{theme}"
    
    # 风格描述
    styles = {
        "摄影风格": "摄影风格，高清8K，色彩明亮，柔和自然光线",
        "动画风格": "卡通动画风格，色彩鲜艳，线条流畅，Pixar风格",
        "水彩风格": "水彩插画风格，柔和色调，手绘质感",
        "电影风格": "电影质感，浅景深，暖色调，电影感光影",
    }
    
    style_desc = styles.get(style, style)
    
    # 构图建议
    compositions = ["中心构图", "三分法构图", "前景中景背景分层"]
    
    prompt = f"{base}，{style_desc}，{compositions[0]}"
    return prompt


def generate_video_prompt(
    subject_action: str,
    camera: str = None,
    mood: str = None,
    direction: str = None
) -> str:
    """生成图生视频提示词"""
    
    parts = []
    
    # 1. 主体动作
    if subject_action:
        parts.append(subject_action)
    
    # 2. 运动方向
    if direction:
        parts.append(f"从{direction}")
    
    # 3. 镜头运动
    if camera:
        parts.append(camera)
    else:
        parts.append("镜头轻微跟随")
    
    # 4. 节奏情绪
    if mood:
        parts.append(mood)
    
    # 5. 环境细节
    parts.append("光线柔和自然")
    
    return "，".join(parts)


def interactive_mode():
    """交互式生成提示词"""
    print("=" * 60)
    print("🎬 提示词生成器")
    print("=" * 60)
    print("输入场景描述，自动生成文生图+图生视频提示词")
    print("(输入 q 退出)\n")
    
    while True:
        print("-" * 40)
        theme = input("📝 场景描述 (例如: 一个小男孩在教室里学编程): ").strip()
        if theme.lower() in ['q', 'quit', 'exit']:
            print("再见!")
            break
        
        if not theme:
            print("请输入场景描述\n")
            continue
        
        print("\n" + "=" * 60)
        print("📸 文生图提示词:")
        print("=" * 60)
        
        # 提取主体
        subject = None
        for s in ["小男孩", "小女孩", "老师", "小男孩小女孩"]:
            if s in theme:
                subject = s
                break
        
        image_prompt = generate_image_prompt(theme, subject)
        print(f"\n{image_prompt}\n")
        
        print("-" * 40)
        print("🎬 图生视频提示词:")
        print("-" * 40)
        
        # 生成几个选项
        print("\n【推荐提示词】\n")
        
        if subject:
            for i, verb in enumerate(SUBJECT_VERBS.get(subject, [])[:3], 1):
                action = f"{subject}{verb}"
                camera = CAMERA_MOVEMENTS[i % len(CAMERA_MOVEMENTS)]
                mood = MOOD_TEMPOS[i % len(MOOD_TEMPOS)]
                video_prompt = generate_video_prompt(action, camera, mood)
                print(f"  方案{i}: {video_prompt}\n")
        else:
            # 通用模式
            print(f"  方案1: {generate_video_prompt('镜头缓慢推近', '镜头缓慢推近', '动作轻柔缓慢')}\n")
            print(f"  方案2: {generate_video_prompt('场景轻微晃动', '镜头轻微拉远', '动作自然流畅')}\n")
            print(f"  方案3: {generate_video_prompt('光线渐变', '镜头固定', '节奏舒缓')}\n")
        
        print("-" * 40)
        print("💡 使用建议:")
        print("-" * 40)
        print("  1. 选择或修改以上提示词")
        print("  2. 将图生视频提示词填入 wan2.2 工作流的正向提示词")
        print("  3. 生成后查看效果，不满意再调整\n")


def cli_mode(theme: str):
    """命令行模式"""
    print("=" * 60)
    print(f"📝 场景: {theme}")
    print("=" * 60)
    
    print("\n📸 文生图提示词:")
    print("-" * 40)
    print(f"\n{generate_image_prompt(theme)}\n")
    
    print("\n🎬 图生视频提示词:")
    print("-" * 40)
    print(f"\n  方案1: {generate_video_prompt('主体轻微前倾', '镜头缓慢推近', '动作轻柔缓慢')}")
    print(f"\n  方案2: {generate_video_prompt('主体转头', '镜头跟随', '动作自然流畅')}")
    print(f"\n  方案3: {generate_video_prompt('主体抬手', '镜头轻微拉远', '动作轻快活泼')}\n")


def main():
    if len(sys.argv) > 1:
        cli_mode(sys.argv[1])
    else:
        interactive_mode()


if __name__ == "__main__":
    main()

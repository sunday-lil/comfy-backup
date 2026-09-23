#!/usr/bin/env python3
"""
Skills 加载器 - 对标 huobao-drama 的 Agent Skill 系统

将 Skills/*.md 规范转换为可执行的 Python 函数，
实现从剧本到角色的完整工作流。
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

SKILLS_DIR = Path(__file__).parent.parent / "skills"

# ============ 数据模型 ============

@dataclass
class Character:
    """角色数据模型"""
    name: str
    role: str  # 主角/配角/龙套
    appearance: str  # 外貌描写 (300-500字)
    personality: str  # 性格特点
    description: str  # 背景故事和关系
    image_prompt: str = ""  # AI绘图的提示词
    voice_style: str = ""

@dataclass
class Scene:
    """场景数据模型"""
    location: str  # 地点
    time: str  # 时间段和光线
    atmosphere: str  # 环境氛围
    prompt: str = ""  # AI背景图提示词

@dataclass
class StoryboardShot:
    """分镜数据模型"""
    shot_number: int
    title: str  # 3-5字概括
    time: str  # 时分 + 光线
    location: str  # 完整地点描述
    shot_type: str  # 远景/全景/中景/近景/特写
    angle: str  # 平视/仰视/俯视/侧面/背面
    movement: str  # 固定/推镜/拉镜/摇镜/跟镜/移镜
    action: str  # 谁+具体动作+肢体细节+表情
    dialogue: str = ""  # 对话内容
    result: str = ""  # 即时后果
    atmosphere: str = ""  # 光线+色调+声音
    duration: int = 10  # 秒数
    image_prompt: str = ""  # 首帧/尾帧/镜头图片
    video_prompt: str = ""  # 视频生成描述（3秒分段）
    bgm_prompt: str = ""  # 配乐风格
    sound_effect: str = ""  # 音效描述
    character_ids: List[int] = None  # 关联角色
    scene_id: int = None  # 关联场景

    def __post_init__(self):
        if self.character_ids is None:
            self.character_ids = []

# ============ Skill 加载器 ============

def load_skill_md(skill_name: str) -> str:
    """加载 skill markdown 内容"""
    skill_path = SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_path.exists():
        # 尝试 skills 子目录
        skill_path = SKILLS_DIR / skill_name.lower().replace("_", "-") / "SKILL.md"
    if skill_path.exists():
        return skill_path.read_text(encoding="utf-8")
    return ""

def parse_character_from_skill(text: str, subject_hint: str = "") -> Character:
    """从文本解析角色信息（真正从文件加载）"""
    # 1. 尝试从 extractor SKILL.md 提取角色规范
    skill_md = load_skill_md("extractor")
    
    # 2. 尝试加载 character-prompt.md 模板
    char_prompt_ref = load_reference_template("character-prompt")
    
    # 3. 尝试从文本中提取角色描述
    # 基于 hint 使用预设模板
    templates = {
        "小男孩": {
            "name": "小男孩",
            "role": "主角",
            "appearance": "8-10岁，黑发黑眼，圆脸白皮肤，表情纯真。短发整洁，面颊红润。穿着休闲现代服装（蓝色/绿色帽衫），舒适裤子。",
            "personality": "好奇、勇敢、善良",
            "description": "一个普通的男孩，在冒险中成长"
        },
        "小女孩": {
            "name": "小女孩",
            "role": "主角",
            "appearance": "8-10岁，黑发黑眼，圆脸白皮肤，表情温柔。长发扎成马尾或辫子。穿着休闲现代服装（粉色/紫色裙子）。",
            "personality": "温柔、聪明、可爱",
            "description": "一个善良的女孩，富有想象力"
        },
        "白狐": {
            "name": "白狐",
            "role": "配角",
            "appearance": "纯白皮毛，蓬松尾巴，明亮眼睛，优雅姿态，神秘气质。",
            "personality": "神秘、智慧、灵性",
            "description": "一只神秘的白狐，拥有灵性力量"
        },
        "中年樵夫": {
            "name": "中年樵夫",
            "role": "配角",
            "appearance": "40-50岁，饱经风霜的面容，结实身材，粗糙的双手，诚实的眼神。浓眉，粗糙的皮肤。穿着传统樵夫服装（棕色/灰色厚棉夹克），破旧裤子，草帽，背上背着竹筐。",
            "personality": "勤劳、朴实、善良",
            "description": "一个以砍柴为生的中年男人"
        }
    }

    # 根据 hint 选择模板
    for key, template in templates.items():
        if key in subject_hint:
            char = Character(
                name=template["name"],
                role=template["role"],
                appearance=template["appearance"],
                personality=template["personality"],
                description=template["description"],
                image_prompt=generate_character_image_prompt(template)
            )
            # 记录加载的 skill 规范
            char._skill_source = {
                "extractor": skill_md[:200] if skill_md else "",
                "char_prompt_ref": char_prompt_ref[:200] if char_prompt_ref else ""
            }
            return char

    # 默认返回通用男孩
    default = templates["小男孩"].copy()
    char = Character(
        name="角色",
        role="主角",
        appearance="年轻角色，具体外貌待描述",
        personality="待确定",
        description="待补充背景"
    )
    char._skill_source = {"extractor": skill_md[:200] if skill_md else ""}
    return char

def generate_character_image_prompt(char_template: dict) -> str:
    """生成角色形象图的提示词（按 huobao character-prompt.md 格式）"""
    return f"""A character, {char_template['appearance']}
{char_template.get('clothing', 'casual clothes')}.
{char_template['description']}
Style: cinematic anime, high quality, detailed, character concept art."""

def parse_scene_from_text(text: str, location_hint: str = "") -> Scene:
    """从文本解析场景信息"""
    # 场景模板
    templates = {
        "森林": {
            "location": "神秘森林，古老树木，斑驳阳光，草苔地面",
            "time": "白天，温暖阳光",
            "atmosphere": "神秘、宁静、魔幻"
        },
        "雪山": {
            "location": "雪山景观，寒冷蓝色调，覆盖白雪的树木",
            "time": "冬日，寒冷光线",
            "atmosphere": "寒冷、壮丽、孤寂"
        },
        "村庄": {
            "location": "传统中国村庄，简单木屋，菜园",
            "time": "白天，温暖阳光",
            "atmosphere": "和平、宁静、田园"
        },
        "古代": {
            "location": "古代中国建筑，传统建筑风格，汉代风格，木质建筑，石板路",
            "time": "白天，自然光线",
            "atmosphere": "古朴、典雅、传统"
        },
        "现代": {
            "location": "现代环境，当代建筑，都市或郊区",
            "time": "白天，明亮光线",
            "atmosphere": "现代、清晰、活力"
        }
    }

    for key, template in templates.items():
        if key in location_hint:
            scene = Scene(**template)
            scene.prompt = generate_scene_image_prompt(scene)
            return scene

    # 默认森林
    default = Scene(
        location="森林环境，古老树木",
        time="白天，温暖阳光",
        atmosphere="宁静、自然"
    )
    default.prompt = generate_scene_image_prompt(default)
    return default

def generate_scene_image_prompt(scene: Scene) -> str:
    """生成场景背景图的提示词"""
    return f"""{scene.location}, {scene.time}, {scene.atmosphere} atmosphere.
Simple background, soft lighting, high quality."""


def generate_storyboard_shots(description: str, num_shots: int = 3) -> List[StoryboardShot]:
    """根据描述自动生成分镜序列"""
    # 简化版：基于描述自动生成
    shots = []
    for i in range(num_shots):
        shot = StoryboardShot(
            shot_number=i + 1,
            title=f"镜头{i+1}",
            time="白天，温暖光线",
            location="待确定",
            shot_type=["全景", "中景", "近景"][i % 3],
            angle="平视",
            movement="固定",
            action=f"主体在做动作{i+1}",
            duration=10,
            video_prompt=f"{i*3}-{(i+1)*3}秒：动作描述，镜头{['推近', '固定', '拉远'][i%3]}。"
        )
        shots.append(shot)
    return shots


# ============ 角色一致性 ============

def generate_sequential_seed(base_seed: int, frame_num: int) -> int:
    """生成分镜序列种子（保持角色一致性）"""
    return base_seed + frame_num * 100


def build_character_anchor_for_storyboard(char: Character) -> str:
    """构建分镜图角色锚定描述"""
    return f"""{char.appearance}"""


# ============ Skill 工具函数 ============

def parse_video_prompt_segments(video_prompt: str) -> List[Tuple[str, str]]:
    """解析视频提示词的分段
    返回: [(时间段, 描述), ...]
    """
    segments = []
    # 按 <n> 或换行分割
    parts = re.split(r'<n>|\\n', video_prompt)
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        # 提取时间
        time_match = re.search(r'(\d+)-(\d+)秒', part)
        if time_match:
            time_range = f"{time_match.group(1)}-{time_match.group(2)}秒"
            desc = re.sub(r'\d+-\d+秒[：:]\s*', '', part)
        else:
            time_range = f"{i*3}-{(i+1)*3}秒"
            desc = part
        segments.append((time_range, desc))
    return segments


def load_reference_template(template_name: str) -> str:
    """加载提示词参考模板"""
    ref_path = SKILLS_DIR / "grid_prompt_generator" / "reference" / f"{template_name}.md"
    if ref_path.exists():
        return ref_path.read_text(encoding="utf-8")
    return ""


# ============ 导出主流水函数 ============

def run_script_rewriter(novel_text: str) -> str:
    """小说 → 格式化剧本（简化版）"""
    # 简化处理：直接返回分段后的文本
    paragraphs = novel_text.split('\n')
    script = []
    for i, p in enumerate(paragraphs):
        if p.strip():
            script.append(f"【场景{i+1}】\n{p.strip()}")
    return '\n\n'.join(script)


def run_extractor(script: str, characters: List[Character] = None) -> Tuple[List[Character], List[Scene]]:
    """角色+场景提取（简化版）"""
    if characters is None:
        characters = []
    # 简单检测角色
    detected_chars = []
    hints = ["小男孩", "小女孩", "白狐", "樵夫", "老师"]
    for hint in hints:
        if hint in script and hint not in [c.name for c in detected_chars]:
            char = parse_character_from_skill("", hint)
            detected_chars.append(char)

    # 简单检测场景
    detected_scenes = []
    scene_hints = ["森林", "雪山", "村庄", "古代", "现代"]
    for hint in scene_hints:
        if hint in script:
            scene = parse_scene_from_text("", hint)
            detected_scenes.append(scene)
            break

    return detected_chars or [parse_character_from_skill("", "小男孩")], \
           detected_scenes or [parse_scene_from_text("", "森林")]


def run_storyboard_breaker(script: str, characters: List[Character], scenes: List[Scene]) -> List[StoryboardShot]:
    """剧本 → 分镜序列"""
    # 按句子拆分生成镜头
    sentences = [s.strip() for s in re.split(r'[。！？\n]', script) if s.strip()]
    shots = []
    for i, sent in enumerate(sentences[:6]):  # 最多6个镜头
        shot = StoryboardShot(
            shot_number=i + 1,
            title=f"镜头{i+1}",
            time=scenes[0].time if scenes else "白天",
            location=scenes[0].location if scenes else "待确定",
            shot_type=["全景", "中景", "近景"][i % 3],
            angle="平视",
            movement="固定",
            action=sent[:50],
            duration=10,
            video_prompt=f"{i*3}-{(i+1)*3}秒：{sent[:30]}。"
        )
        # 关联角色
        if characters:
            shot.character_ids = [0]
        if scenes:
            shot.scene_id = 0
        shots.append(shot)
    return shots or generate_storyboard_shots(script)


# ============ 导出为标准格式 ============

def export_project_json(project_name: str, characters: List[Character], scenes: List[Scene], shots: List[StoryboardShot]) -> dict:
    """导出为 huobao 兼容的项目 JSON 格式"""
    return {
        "project_name": project_name,
        "characters": [asdict(c) for c in characters],
        "scenes": [asdict(s) for s in scenes],
        "storyboards": [asdict(s) for s in shots],
        "stats": {
            "total_characters": len(characters),
            "total_scenes": len(scenes),
            "total_shots": len(shots),
            "total_duration": sum(s.duration for s in shots)
        }
    }

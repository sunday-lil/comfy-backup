#!/usr/bin/env python3
"""
短视频生成主流水线 - 完整自动化
描述 → 定妆照 → 分镜图 → 分镜视频 → 短片

全程只输入简单描述，提示词及动作由系统自动完成补充。

用法:
    # 交互模式（推荐）— Windows 用 py，Linux/Mac 用 python
    py main_pipeline.py --interactive
    
    # 一键模式
    py main_pipeline.py -d "一个小男孩在森林里遇到一只白狐" -t "从前有个小男孩..."
    
    # 先生成定妆照（多次种子尝试）
    py main_pipeline.py -d "描述" --costume-only
    
    # 基于已有定妆照生成分镜
    py main_pipeline.py -d "描述" --use-costume projects/xxx/costume_photos/xxx.png
"""

import argparse
import json
import os
import sys
import time
import random
import requests
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

# ============ 配置 ============
# 所有地址/路径均可用同名环境变量覆盖（Windows 下 set XXX=yyy，PowerShell 下 $env:XXX="yyy"）
WORKFLOW_DIR = Path(__file__).parent
OUTPUT_DIR = WORKFLOW_DIR / "output"
PROJECTS_DIR = WORKFLOW_DIR / "projects"

COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/v1/chat/completions")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
FISH_SPEECH_API = os.environ.get("FISH_SPEECH_API", "http://localhost:8080/v1/tts")
# fish-speech 安装目录（S1-mini 版代码 + venv + checkpoints）
FISH_SPEECH_DIR = os.environ.get("FISH_SPEECH_DIR", r"D:\fish-speech-main")

# ComfyUI 的 input 目录（必须是真实的 ComfyUI/input，图片会复制进去供 LoadImage 读取）
# 默认指向本机便携版安装位置，可用环境变量 COMFYUI_INPUT_DIR 覆盖
COMFYUI_INPUT_DIR = Path(os.environ.get("COMFYUI_INPUT_DIR", r"D:\comfy\ComfyUI_windows_portable\ComfyUI\input"))
# 生成文件的下载缓存目录（不必是真实的 ComfyUI/output，脚本通过 HTTP /view 下载到这里）
COMFYUI_OUTPUT_DIR = Path(os.environ.get("COMFYUI_OUTPUT_DIR", str(WORKFLOW_DIR / "output" / "comfyui_downloads")))

# 工作流模板
TXT2IMG_WORKFLOW = WORKFLOW_DIR / "文生图.json"
I2V_WORKFLOW_TEMPLATE = WORKFLOW_DIR / "shot1_i2v.json"  # 原始无参考
I2V_WORKFLOW_REFERENCE = WORKFLOW_DIR / "shot1_i2v_reference.json"  # 带CLIP Vision参考

# ============ 角色锚定模板库 ============
# 每个角色包含：基础描述 + 详细特征（服装/发型/配饰）+ 一致性关键词

# ============ 可配置的模板库 ============
# 这些模板用于补充描述中未指定的元素

CHARACTER_TEMPLATES = {
    # 基础角色模板（年龄、性别可覆盖）
    "default": {
        "anchor": "A person",
        "appearance": "",
        "clothing": "casual clothes",
        "accessories": "",
        "style": "photorealistic, high quality, 8K, detailed face"
    },
    "小男孩": {
        "anchor": "A young Chinese boy, 8-10 years old, black hair, black eyes, round face, fair skin, innocent expression",
        "appearance": "black short hair, no hat, clean face, rosy cheeks",
        "clothing": "casual modern hoodie (blue/green color), comfortable pants",
        "accessories": "small backpack",
        "style": "photorealistic, high quality, 8K, bright colors, soft lighting, detailed face"
    },
    "小女孩": {
        "anchor": "A young Chinese girl, 8-10 years old, black hair, black eyes, round face, fair skin, gentle expression",
        "appearance": "black long hair braided or ponytail, clean face, rosy cheeks",
        "clothing": "casual modern dress (pink/purple color) or casual clothes",
        "accessories": "hair ribbon or clip",
        "style": "photorealistic, high quality, 8K, bright colors, soft lighting, detailed face"
    },
    "白狐": {
        "anchor": "A beautiful white fox with fluffy white fur, bright eyes, elegant posture",
        "appearance": "pure white fur, fluffy tail, bright intelligent eyes, mystical aura",
        "clothing": "none (animal)",
        "accessories": "none",
        "style": "fantasy art, high quality, 8K, ethereal lighting, soft colors, detailed fur"
    },
    "小男孩和白狐": {
        "anchor": "A young Chinese boy (8-10 years old) with black hair, black eyes, round face, fair skin, innocent expression; A beautiful white fox with pure white fluffy fur, bright eyes, elegant posture",
        "appearance": "boy: black short hair, innocent smile; fox: pure white fur, fluffy tail, alert ears",
        "clothing": "boy: casual modern hoodie (blue), small backpack on back; fox: none",
        "accessories": "boy: small backpack; fox: mystical glow",
        "style": "fantasy realistic, high quality, 8K, ethereal lighting, soft colors, harmonious composition"
    },
    "中年樵夫": {
        "anchor": "A middle-aged Chinese woodcutter, 40-50 years old, weathered face, kind eyes, rough hands, honest expression",
        "appearance": "weathered face, rough hands showing years of work, thick eyebrows, honest and kind expression",
        "clothing": "traditional woodcutter clothes, thick cotton jacket (brown/gray), worn pants, straw sandals",
        "accessories": "bamboo hat, carrying basket on back",
        "style": "Shaw Brothers cinema style, classic Hong Kong film aesthetic, cinematic, high quality"
    },
}

# 物品模板库（用于识别描述中的物品）
OBJECT_TEMPLATES = {
    "酱板鸭": "a piece of roasted salted duck (Chinese cuisine), brown crispy skin, on a small plate or wrapped in paper",
    "背包": "small backpack, casual style, worn on back",
    "树叶": "green leaves, forest setting",
    "花": "colorful wildflowers",
    "树枝": "tree branch, wooden",
    "帽子": "casual hat or bamboo hat",
    "篮子": "small basket, woven",
    "面包": "bread or steamed bun",
    "担架": "wooden carrying pole, traditional style",
    "斧头": "sharp axe, woodcutter's tool, iron blade, wooden handle",
}

# 动作模板库（用于识别描述中的动作）
ACTION_TEMPLATES = {
    "相遇": "gazing at each other with curiosity, standing face to face, eyes meeting",
    "打招呼": "waving hand gently, smiling at each other, nodding head",
    "送东西": "offering something with hand, placing item gently, extending arm holding object",
    "接收": "accepting with both hands gratefully, receiving item carefully, holding item gently",
    "感谢": "smiling gratefully, bowing slightly, eyes showing gratitude",
    "离开": "waving goodbye, turning to leave, looking back",
    "跟随": "walking side by side, following behind, together journey",
    "看": "gazing at something, looking at each other, observing carefully",
    "吃": "eating food, enjoying meal, tasting something delicious",
    "蹲下": "crouching down slowly, kneeling on one knee, bending at waist",
    "躺下": "lying down gently, resting on side, lying on ground",
    "站着": "standing tall, standing still, standing in place",
    "走来": "walking toward, approaching slowly, stepping forward",
    "掏出": "reaching into bag, taking out item, pulling something from backpack",
    "放下": "placing item on ground gently, setting something down carefully",
}

# 场景模板库（用于识别描述中的场景）
SCENE_TEMPLATES = {
    "森林": "mystical forest, ancient tall trees, soft dappled sunlight, mossy ground, fallen leaves, ethereal atmosphere, fairy tale setting",
    "树林": "dense forest, variety of trees, green undergrowth, natural clearing, peaceful woods",
    "草地": "lush green meadow, soft grass, scattered wildflowers, gentle breeze",
    "小溪": "small stream, crystal clear water, smooth stones, gentle flowing water sound",
    "雪山": "snowy mountain landscape, snow-covered trees, cold blue tones, winter atmosphere, white snow everywhere",
    "雪地": "snowy ground, white snow covering everything, cold winter setting, snowflakes in air",
    "村庄": "traditional Chinese village, simple wooden houses, vegetable garden, peaceful countryside",
    "古代": "ancient Chinese setting, traditional architecture, Han dynasty style, wooden buildings, stone paths",
    "现代": "modern setting, contemporary environment, urban or suburban area",
}

# 风格模板库（用于识别描述中的艺术风格）
STYLE_TEMPLATES = {
    "邵氏电影": {
        "name": "Shaw Brothers Style",
        "prompt": "Shaw Brothers cinema style, classic 1960s-70s Hong Kong martial arts film aesthetic, warm desaturated colors, dramatic lighting, film grain, anamorphic lens flare, vintage cinematic look, traditional Chinese setting",
        "negative": "modern, sci-fi, CGI, anime, cartoon"
    },
    "邵氏": {
        "name": "Shaw Brothers Style",
        "prompt": "Shaw Brothers cinema style, classic 1960s-70s Hong Kong martial arts film aesthetic, warm desaturated colors, dramatic lighting, film grain, vintage cinematic look, traditional Chinese setting",
        "negative": "modern, sci-fi, CGI, anime, cartoon"
    },
    "武侠电影": {
        "name": "Martial Arts Cinema",
        "prompt": "classic martial arts movie style, dramatic Chinese cinema, heroic atmosphere, traditional costumes, sword fighting scenes, atmospheric lighting",
        "negative": "modern, sci-fi"
    },
    "皮克斯": {
        "name": "Pixar Style",
        "prompt": "Pixar animation style, vibrant colors, expressive characters, smooth animation, high quality 3D render, studio animation quality",
        "negative": "photorealistic, live action"
    },
    "写实": {
        "name": "Photorealistic",
        "prompt": "photorealistic, high quality, 8K, detailed face, natural lighting, lifelike texture",
        "negative": "anime, cartoon, painting, illustration"
    },
    "动漫": {
        "name": "Anime Style",
        "prompt": "anime style, Japanese animation aesthetic, vibrant colors, clean linework, cel shading",
        "negative": "photorealistic, live action"
    },
    "水墨": {
        "name": "Chinese Ink Wash Style",
        "prompt": "Chinese ink wash painting style, traditional brushstroke aesthetic, monochrome gray tones, sumi-e, elegant brushwork",
        "negative": "colorful, bright, modern"
    },
    "古风": {
        "name": "Ancient Chinese Style",
        "prompt": "ancient Chinese aesthetic, traditional Hanfu clothing, classical Chinese art style, historical accuracy, cultural authenticity",
        "negative": "modern, Western"
    },
}

# ============ 工具函数 ============

def check_service(url: str, timeout: int = 5) -> bool:
    """检查服务是否运行"""
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except:
        return False

def check_comfyui() -> bool:
    return check_service(f"{COMFYUI_URL}/system_stats")

def check_fish_speech() -> bool:
    try:
        return check_service(f"{FISH_SPEECH_API.replace('/v1/tts', '/v1/health')}")
    except:
        return False

# 本进程启动的 fish 服务器（用于 TTS 完成后释放显存）
_fish_process = None

def start_fish_server(wait_seconds: int = 150) -> bool:
    """按需启动 fish-speech API 服务器（TTS 阶段专用，用完释放显存给 ComfyUI）"""
    global _fish_process
    if check_fish_speech():
        print("  [Fish Speech] 已在运行，直接使用")
        return True

    fish_dir = Path(FISH_SPEECH_DIR)
    python_exe = fish_dir / "venv" / "Scripts" / "python.exe"
    if not python_exe.exists():
        print(f"  ⚠️ 未找到 fish-speech venv: {python_exe}")
        return False

    log_path = WORKFLOW_DIR / "setup" / "logs" / "fish_api.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(python_exe), "-m", "tools.api_server",
        "--listen", "127.0.0.1:8080",
        "--llama-checkpoint-path", "checkpoints/openaudio-s1-mini",
        "--decoder-checkpoint-path", "checkpoints/openaudio-s1-mini/codec.pth",
        "--decoder-config-name", "modded_dac_vq",
    ]
    print("  [Fish Speech] 启动服务器（加载模型约 30-60 秒）...")
    log_file = open(log_path, "w", encoding="utf-8")
    _fish_process = subprocess.Popen(
        cmd, cwd=str(fish_dir), stdout=log_file, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    import time as _time
    for i in range(wait_seconds // 3):
        _time.sleep(3)
        if check_fish_speech():
            print("  [Fish Speech] 服务器就绪")
            return True
        if _fish_process.poll() is not None:
            print(f"  ⚠️ Fish Speech 进程退出 (code={_fish_process.returncode})，日志: {log_path}")
            return False
    print("  ⚠️ Fish Speech 启动超时")
    return False

def stop_fish_server():
    """停止本进程启动的 fish 服务器，释放显存（不影响外部已运行的实例）"""
    global _fish_process
    if _fish_process is None:
        return
    try:
        _fish_process.terminate()
        try:
            _fish_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _fish_process.kill()
        print("  [Fish Speech] 已停止（显存已释放）")
    except Exception as e:
        print(f"  ⚠️ 停止 Fish Speech 失败: {e}")
    finally:
        _fish_process = None

def create_project_dir(project_name: str) -> Path:
    """创建项目目录"""
    project_dir = PROJECTS_DIR / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "costume_photos").mkdir(exist_ok=True)
    (project_dir / "storyboards").mkdir(exist_ok=True)
    (project_dir / "videos").mkdir(exist_ok=True)
    (project_dir / "audio").mkdir(exist_ok=True)
    return project_dir

def generate_seed() -> int:
    """生成随机种子"""
    return random.randint(100000000000000, 999999999999999)

# ============ 提示词生成 ============

# ============ LLM 智能解析 ============

LLM_SYSTEM_PROMPT = """You are a story element extraction assistant. Analyze the user's story description and extract ALL elements. Return ONLY valid JSON with English text.

Output format (ALL in English):
{
    "subjects": [
        {
            "name": "character name in Chinese/Pinyin",
            "age": "age description in English (e.g., 'middle-aged', 'child')",
            "gender": "male/female/unknown",
            "appearance": "appearance description in English",
            "clothing": "clothing description in English (e.g., 'thick cotton padded winter clothes')",
            "accessories": "accessories in English (e.g., 'bamboo hat, carrying basket')",
            "pose": "pose/action in English (e.g., 'lying in snow, kneeling down')"
        }
    ],
    "objects": [
        {
            "name": "object name in Chinese",
            "description": "object description in English"
        }
    ],
    "scene": "scene description in English, include lighting and atmosphere",
    "style": "art style in English (e.g., 'Shaw Brothers cinema style')",
    "mood": "mood in English (e.g., 'warm, touching')",
    "camera": "camera suggestion in English (e.g., 'close-up, tracking shot')"
}

IMPORTANT:
- ALL descriptions MUST be in English, not Chinese
- clothing must match era and weather (snow = winter padded clothes)
- scene should include lighting details
- Return ONLY JSON, no other text"""

def parse_with_llm(description: str) -> dict:
    """使用 LLM 智能解析故事描述"""
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": f"请分析以下故事描述，提取所有元素：\n\n{description}"}
            ],
            "temperature": 0.1,
            "stream": False
        }

        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        # 提取 JSON（支持多种格式）
        json_str = content.strip()
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0]
        json_str = json_str.strip()

        parsed = json.loads(json_str)

        # ========== 标准化输出格式以匹配代码期望 ==========

        # 1. subjects - 转换为列表格式
        subjects_raw = parsed.get("subjects", [])
        if isinstance(subjects_raw, list):
            subjects = []
            for s in subjects_raw:
                if isinstance(s, dict):
                    subjects.append(s.get("name", str(s)))
                else:
                    subjects.append(str(s))
        else:
            subjects = [str(subjects_raw)]

        # 2. objects - 统一为 {keyword, name, description} 格式（与规则解析路径一致）
        objects = parsed.get("objects", [])
        if not isinstance(objects, list):
            objects = []
        norm_objects = []
        for o in objects:
            if isinstance(o, dict):
                kw = o.get("keyword") or o.get("name") or ""
                norm_objects.append({"keyword": kw, "name": o.get("name", kw), "description": o.get("description", "")})
            else:
                norm_objects.append({"keyword": str(o), "name": str(o), "description": ""})
        objects = norm_objects

        # 3. style - 转换为代码期望的格式
        style_raw = parsed.get("style", "")
        style_info = None
        if style_raw:
            # 检查是否是已知的风格关键词
            style_key = None
            for key in STYLE_TEMPLATES.keys():
                if key in str(style_raw) or key.replace("电影", "") in str(style_raw):
                    style_key = key
                    break
            if style_key:
                style_info = {
                    "keyword": style_key,
                    "name": STYLE_TEMPLATES[style_key]["name"],
                    "prompt": STYLE_TEMPLATES[style_key]["prompt"],
                    "negative": STYLE_TEMPLATES[style_key]["negative"]
                }
            else:
                # 未知风格，使用原始值
                style_info = {
                    "keyword": str(style_raw),
                    "name": str(style_raw),
                    "prompt": str(style_raw),
                    "negative": ""
                }

        # 4. scene - 保持原样
        scene = parsed.get("scene", "")

        # 5. mood - 保持原样
        mood = parsed.get("mood", "gentle")

        # 6. camera - 保持原样
        camera = parsed.get("camera", "")

        # 7. 构建标准化输出
        normalized = {
            "subjects": subjects,           # ['白狐', '樵夫']
            "subjects_detail": parsed.get("subjects", []),  # 原始详细信息
            "objects": objects,             # [{name, description}, ...]
            "actions": [],                  # 待后续从动作词提取
            "scene": scene,                 # 场景描述
            "mood": mood,                   # 情绪
            "style": style_info,            # {keyword, name, prompt, negative}
            "camera": camera,               # 镜头建议
            "original": description          # 原始输入
        }

        print(f"\n[LLM解析] 成功")
        print(f"  角色: {subjects}")
        print(f"  物品: {[o.get('name') if isinstance(o, dict) else o for o in objects]}")
        print(f"  场景: {scene[:50]}...")
        print(f"  风格: {style_info.get('name') if style_info else '默认'}")
        print(f"  情绪: {mood}")

        return normalized

    except Exception as e:
        print(f"\n[LLM解析] 失败: {e}，使用规则解析")
        return _parse_description_rules(description)


def parse_description(description: str, use_llm: bool = True) -> dict:
    """解析描述，提取角色、物品、动作、场景、风格等所有关键元素

    优先使用 LLM 智能解析，如失败则使用备用规则解析。
    """
    # 优先使用 LLM 解析
    if use_llm:
        print(f"\n[解析] 使用 LLM 智能解析...")
        return parse_with_llm(description)
    result = {
        "subjects": [],           # 检测到的角色
        "objects": [],           # 检测到的物品
        "actions": [],          # 检测到的动作
        "scene": "",             # 场景描述
        "mood": "gentle",       # 情绪
        "style": None,           # 艺术风格
        "original": description  # 原始输入
    }

    desc_lower = description.lower()

    # ========== 1. 检测艺术风格 ==========
    for style_keyword, style_info in STYLE_TEMPLATES.items():
        if style_keyword in description:
            result["style"] = {
                "keyword": style_keyword,
                "name": style_info["name"],
                "prompt": style_info["prompt"],
                "negative": style_info["negative"]
            }
            break

    # ========== 2. 检测角色 ==========
    # 基于关键词匹配，按优先级排序（长词优先）
    character_keywords = [
        ("中年樵夫", "中年樵夫"),
        ("中年男人", "中年樵夫"),
        ("小女孩", "小女孩"),
        ("小男孩", "小男孩"),
        ("白狐", "白狐"),
        ("樵夫", "中年樵夫"),  # 默认中年樵夫
        ("女孩", "小女孩"),
        ("男孩", "小男孩"),
    ]

    detected_subjects = []
    for keyword, subject_type in character_keywords:
        if keyword in description:
            if subject_type not in detected_subjects:
                detected_subjects.append(subject_type)

    # 复合角色检测 - 按优先级
    has_fox = "白狐" in description
    has_middle_age = any(s in description for s in ["中年", "成年", "老"])
    has_boy = any(s in description for s in ["男孩", "小男孩"])
    has_girl = any(s in description for s in ["女孩", "小女孩"])
    has_woodcutter = "樵夫" in description

    if has_fox:
        if has_woodcutter and has_middle_age:
            detected_subjects = ["中年樵夫", "白狐"]
        elif has_boy and not has_girl:
            detected_subjects = ["小男孩和白狐"]
        elif has_girl:
            detected_subjects = ["小女孩和白狐"]
        else:
            detected_subjects = ["白狐"]
    elif has_woodcutter:
        detected_subjects = ["中年樵夫"]
    elif has_middle_age and not has_girl:
        detected_subjects = ["中年樵夫"]
    elif has_boy and not has_girl:
        detected_subjects = ["小男孩"]
    elif has_girl:
        detected_subjects = ["小女孩"]

    result["subjects"] = detected_subjects if detected_subjects else ["小男孩"]

    # ========== 3. 检测物品 ==========
    for obj_keyword, obj_desc in OBJECT_TEMPLATES.items():
        if obj_keyword in description:
            result["objects"].append({
                "keyword": obj_keyword,
                "description": obj_desc
            })

    # ========== 4. 检测动作 ==========
    for action_keyword, action_desc in ACTION_TEMPLATES.items():
        if action_keyword in description:
            result["actions"].append({
                "keyword": action_keyword,
                "description": action_desc
            })

    # ========== 5. 检测场景 ==========
    # 先检查完整短语，再检查单词
    scene_priority = ["雪地", "雪山", "森林", "树林", "草地", "小溪", "村庄", "古代", "现代"]
    for scene_keyword in scene_priority:
        if scene_keyword in description:
            result["scene"] = SCENE_TEMPLATES[scene_keyword]
            break

    if not result["scene"]:
        # 从描述中提取场景关键词
        scene_words = ["雪地", "雪地", "森林", "草地", "河边", "山", "村"]
        for word in scene_words:
            if word in description:
                result["scene"] = SCENE_TEMPLATES.get(word, f"{word} setting")
                break

    # 如果还是没有，使用默认值
    if not result["scene"]:
        result["scene"] = "natural outdoor setting, soft lighting, peaceful atmosphere"

    # ========== 6. 检测情绪 ==========
    mood_keywords = {
        "开心": "happy",
        "快乐": "happy",
        "高兴": "happy",
        "欢快": "happy",
        "神秘": "mysterious",
        "奇幻": "mysterious",
        "魔幻": "mysterious",
        "悲伤": "sad",
        "难过": "sad",
        "温馨": "warm",
        "感人": "touching",
        "紧张": "tense",
        "恐怖": "scary"
    }
    for keyword, mood in mood_keywords.items():
        if keyword in description:
            result["mood"] = mood
            break

    # ========== 7. 检测年龄/外观描述 ==========
    age_descriptions = []
    if "中年" in description:
        age_descriptions.append("middle-aged, 40-50 years old")
    elif "老年" in description or "老人" in description:
        age_descriptions.append("elderly, 60-70 years old")
    elif "少年" in description:
        age_descriptions.append("teenage, 15-18 years old")
    elif "儿童" in description or "小孩" in description:
        age_descriptions.append("child, 6-12 years old")
    elif "年轻" in description:
        age_descriptions.append("young adult, 20-30 years old")

    result["age_descriptions"] = age_descriptions

    # ========== 8. 检测服装风格 ==========
    clothing_keywords = []
    if any(w in description for w in ["古装", "汉服", "古代"]):
        clothing_keywords.append("traditional Chinese ancient clothing, Hanfu")
    if any(w in description for w in ["现代", "休闲"]):
        clothing_keywords.append("modern casual clothing")
    if any(w in description for w in ["棉衣", "棉袄", "冬装"]):
        clothing_keywords.append("thick cotton padded clothes, winter clothing")
    if any(w in description for w in ["樵夫", "农夫", "农民"]):
        clothing_keywords.append("woodcutter farmer clothes, coarse fabric")

    result["clothing_keywords"] = clothing_keywords

    print(f"\n[规则解析] 结果:")
    print(f"  角色: {result['subjects']}")
    print(f"  物品: {[o['keyword'] for o in result['objects']]}")
    print(f"  动作: {[a['keyword'] for a in result['actions']]}")
    print(f"  场景: {result['scene'][:50]}...")
    print(f"  风格: {result['style']['name'] if result['style'] else '默认'}")
    print(f"  情绪: {result['mood']}")

    return result


def _parse_description_rules(description: str) -> dict:
    """基于规则的解析（备用）- 当 LLM 不可用时使用"""
    result = {
        "subjects": [],           # 检测到的角色
        "objects": [],           # 检测到的物品
        "actions": [],          # 检测到的动作
        "scene": "",             # 场景描述
        "mood": "gentle",       # 情绪
        "style": None,           # 艺术风格
        "original": description  # 原始输入
    }

    desc_lower = description.lower()

    # ========== 1. 检测艺术风格 ==========
    for style_keyword, style_info in STYLE_TEMPLATES.items():
        if style_keyword in description:
            result["style"] = {
                "keyword": style_keyword,
                "name": style_info["name"],
                "prompt": style_info["prompt"],
                "negative": style_info["negative"]
            }
            break

    # ========== 2. 检测角色 ==========
    character_keywords = [
        ("中年樵夫", "中年樵夫"),
        ("中年男人", "中年樵夫"),
        ("小女孩", "小女孩"),
        ("小男孩", "小男孩"),
        ("白狐", "白狐"),
        ("樵夫", "中年樵夫"),
        ("女孩", "小女孩"),
        ("男孩", "小男孩"),
    ]

    detected_subjects = []
    for keyword, subject_type in character_keywords:
        if keyword in description:
            if subject_type not in detected_subjects:
                detected_subjects.append(subject_type)

    has_fox = "白狐" in description
    has_middle_age = any(s in description for s in ["中年", "成年", "老"])
    has_boy = any(s in description for s in ["男孩", "小男孩"])
    has_girl = any(s in description for s in ["女孩", "小女孩"])
    has_woodcutter = "樵夫" in description

    if has_fox:
        if has_woodcutter and has_middle_age:
            detected_subjects = ["中年樵夫", "白狐"]
        elif has_boy and not has_girl:
            detected_subjects = ["小男孩和白狐"]
        elif has_girl:
            detected_subjects = ["小女孩和白狐"]
        else:
            detected_subjects = ["白狐"]
    elif has_woodcutter:
        detected_subjects = ["中年樵夫"]
    elif has_middle_age and not has_girl:
        detected_subjects = ["中年樵夫"]
    elif has_boy and not has_girl:
        detected_subjects = ["小男孩"]
    elif has_girl:
        detected_subjects = ["小女孩"]

    result["subjects"] = detected_subjects if detected_subjects else ["小男孩"]

    # ========== 3. 检测物品 ==========
    for obj_keyword, obj_desc in OBJECT_TEMPLATES.items():
        if obj_keyword in description:
            result["objects"].append({
                "keyword": obj_keyword,
                "description": obj_desc
            })

    # ========== 4. 检测动作 ==========
    for action_keyword, action_desc in ACTION_TEMPLATES.items():
        if action_keyword in description:
            result["actions"].append({
                "keyword": action_keyword,
                "description": action_desc
            })

    # ========== 5. 检测场景 ==========
    scene_priority = ["雪地", "雪山", "森林", "树林", "草地", "小溪", "村庄", "古代", "现代"]
    for scene_keyword in scene_priority:
        if scene_keyword in description:
            result["scene"] = SCENE_TEMPLATES[scene_keyword]
            break

    if not result["scene"]:
        scene_words = ["雪地", "森林", "草地", "河边", "山", "村"]
        for word in scene_words:
            if word in description:
                result["scene"] = SCENE_TEMPLATES.get(word, f"{word} setting")
                break

    if not result["scene"]:
        result["scene"] = "natural outdoor setting, soft lighting, peaceful atmosphere"

    # ========== 6. 检测情绪 ==========
    mood_keywords = {
        "开心": "happy", "快乐": "happy", "高兴": "happy", "欢快": "happy",
        "神秘": "mysterious", "奇幻": "mysterious", "魔幻": "mysterious",
        "悲伤": "sad", "难过": "sad",
        "温馨": "warm", "感人": "touching",
        "紧张": "tense", "恐怖": "scary"
    }
    for keyword, mood in mood_keywords.items():
        if keyword in description:
            result["mood"] = mood
            break

    # ========== 7. 检测年龄/外观描述 ==========
    age_descriptions = []
    if "中年" in description:
        age_descriptions.append("middle-aged, 40-50 years old")
    elif "老年" in description or "老人" in description:
        age_descriptions.append("elderly, 60-70 years old")
    elif "少年" in description:
        age_descriptions.append("teenage, 15-18 years old")
    elif "儿童" in description or "小孩" in description:
        age_descriptions.append("child, 6-12 years old")
    elif "年轻" in description:
        age_descriptions.append("young adult, 20-30 years old")

    result["age_descriptions"] = age_descriptions

    # ========== 8. 检测服装风格 ==========
    clothing_keywords = []
    if any(w in description for w in ["古装", "汉服", "古代"]):
        clothing_keywords.append("traditional Chinese ancient clothing, Hanfu")
    if any(w in description for w in ["现代", "休闲"]):
        clothing_keywords.append("modern casual clothing")
    if any(w in description for w in ["棉衣", "棉袄", "冬装"]):
        clothing_keywords.append("thick cotton padded clothes, winter clothing")
    if any(w in description for w in ["樵夫", "农夫", "农民"]):
        clothing_keywords.append("woodcutter farmer clothes, coarse fabric")

    result["clothing_keywords"] = clothing_keywords

    print(f"\n[规则解析] 结果:")
    print(f"  角色: {result['subjects']}")
    print(f"  物品: {[o['keyword'] for o in result['objects']]}")
    print(f"  动作: {[a['keyword'] for a in result['actions']]}")
    print(f"  场景: {result['scene'][:50]}...")
    print(f"  风格: {result['style']['name'] if result['style'] else '默认'}")
    print(f"  情绪: {result['mood']}")

    return result


def _translate_and_clean(text: str, scene: str = "") -> str:
    """翻译中文并清理无效值"""
    if not text or text in ["无", "None", "null", "", "none", "n/a", "N/A"]:
        return ""

    # 完整翻译字典（按长度排序，长的先匹配）
    translations = [
        # 角色外貌
        ("纯白色的皮毛", "pure white fur, fluffy and beautiful"),
        ("全身雪白", "pure white fur, fluffy"),
        ("白色毛发", "white fur"),
        ("白色皮毛", "white fur, clean"),
        ("面容沧桑", "weathered face, experienced look"),
        ("中年男性", "middle-aged man"),
        ("中年男性面孔", "weathered face"),
        ("中年男性", "middle-aged man"),

        # 服装
        ("厚重的冬日粗布衣物或皮草", "thick cotton padded winter clothes, worn but warm, traditional Chinese rural style"),
        ("适合雪地的厚重冬装/樵夫服饰", "thick padded winter clothes suitable for snow, woodcutter style"),
        ("适合雪地厚重冬装/传统樵夫服饰", "thick padded winter clothes suitable for snow, woodcutter traditional style"),
        ("冬装", "winter clothing with thick padding"),
        ("古装", "traditional Chinese ancient clothing, Hanfu"),
        ("thick traditional cotton padded winter clothes suitable for a woodcutter", "thick padded winter clothes, traditional woodcutter style"),
        ("thick cotton padded winter clothes suitable for cold weather", "thick padded winter clothes, traditional style"),

        # 物品
        ("酱板鸭", "roasted salted duck, Chinese cuisine, golden brown color"),
        ("深褐色酱色鸭肉", "golden brown roasted duck meat"),
        ("酱色鸭肉", "sauce-colored duck meat"),
        ("酱色的鸭肉", "sauce-colored duck meat"),
        ("dark, savory braised duck", "savory braised duck, golden brown color"),
        ("鸭肉", "duck meat"),
        ("背包", "backpack"),
        ("竹筐", "bamboo basket"),
        ("斗笠", "bamboo hat"),
        ("篮子", "basket"),
        ("桨板鸭", "roasted salted duck"),
        ("a cloth bag", "cloth bag, worn"),

        # 配饰
        ("背囊/包", "carrying bag on shoulder"),
        ("背囊", "carrying bag"),
        ("竹竿", "bamboo pole"),

        # 姿态/动作
        ("躺在雪地里", "lying peacefully in the snow"),
        ("躺在地上", "lying on the ground"),
        ("蹲下", "kneeling, crouching"),
        ("走进并蹲下", "walking into frame and kneeling down"),
        ("走进画面后蹲下", "walking into the scene and kneeling"),
        ("蹲下，从包里掏出", "kneeling down and taking out from bag"),
        ("walking into the scene, then squatting down to place food", "walking into scene and kneeling, placing food beside"),
        ("walking into the scene, then squatting down", "walking into scene and kneeling"),

        # 物品描述
        ("樵夫随身携带", "worn, used by woodcutter"),
        ("樵夫用来携带物品的包", "worn carrying bag, used by woodcutter"),
        ("用来装东西的包", "practical carrying bag"),
        ("深褐色", "golden brown"),
        ("酱色", "sauce-colored"),

        # 无效值
        ("无", ""),
        ("none", ""),
    ]

    for cn, en in translations:
        text = text.replace(cn, en)

    # 清理
    import re
    text = re.sub(r'\bnone\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bn/?a\b', '', text, flags=re.IGNORECASE)  # n/a, N/A
    text = re.sub(r'\b的\b', ' ', text)  # 助词
    text = re.sub(r'\bthe\b', '', text, flags=re.IGNORECASE)  # 多余冠词
    text = re.sub(r'\s+', ' ', text)  # 多个空格变一个
    text = re.sub(r'^[\s,]+|[\s,]+$', '', text)  # 首尾空白/逗号
    text = re.sub(r',+', ',', text)  # 多余逗号
    text = re.sub(r'\b,+\b', '', text)  # 孤立逗号

    return text.strip()


def _translate_scene(scene: str) -> str:
    """翻译场景描述"""
    if not scene:
        return ""

    # 场景翻译
    scene_translations = [
        ("白雪皑皑的雪地", "snowy white landscape, pristine snow covering everything"),
        ("白雪覆盖的雪地", "snow-covered ground, white snow stretching to horizon"),
        ("寒冷的冬日环境", "cold winter environment"),
        ("寒冷的冬季", "cold winter season"),
        ("寒冷的冬日", "cold winter day"),
        ("环境静谧", "tranquil environment"),
        ("光线柔和", "soft, gentle lighting"),
        ("光线", "lighting"),
        ("雪地", "snowy ground, winter landscape"),
        ("森林", "forest setting, trees surroundings"),
        ("海边", "seaside, ocean background"),
        ("山顶", "mountain top, rocky terrain"),
        ("古代村庄", "ancient Chinese village, traditional architecture"),
        ("现代城市", "modern city, contemporary urban setting"),
        ("草原", "grassland, vast plains"),
    ]

    for cn, en in scene_translations:
        scene = scene.replace(cn, en)

    # 清理残留中文
    import re
    scene = re.sub(r'[^\w\s,.\-]', ' ', scene)
    scene = re.sub(r'\s+', ' ', scene)
    scene = re.sub(r'^[\s,]+|[\s,]+$', '', scene)

    return scene.strip()


def build_character_prompt(subject: str, description: str, parsed: dict, include_style: bool = True, include_pose: bool = True, include_scene: bool = True, include_objects: bool = True) -> str:
    """构建角色提示词

    使用 LLM 解析的详细角色信息 + 全局上下文（场景/风格/物品）

    Args:
        include_pose: 是否包含姿态/动作（定妆照应设为 False）
        include_scene: 是否包含场景（定妆照可设为 False 避免混杂）
        include_objects: 是否包含物品（定妆照应设为 False 避免混杂）
    """
    parts = []

    # ========== 1. 获取角色详细信息 ==========
    # 优先使用 LLM 解析的详细角色信息
    subjects_detail = parsed.get("subjects_detail", [])
    character_detail = None

    for s in subjects_detail:
        if isinstance(s, dict) and s.get("name") == subject:
            character_detail = s
            break
        elif isinstance(s, str) and s == subject:
            character_detail = {"name": subject}
            break

    # 如果没找到，尝试模糊匹配
    if not character_detail and subjects_detail:
        for s in subjects_detail:
            if isinstance(s, dict):
                name = s.get("name", "")
                if subject in name or name in subject:
                    character_detail = s
                    break

    # ========== 2. 构建角色描述 ==========
    if character_detail and isinstance(character_detail, dict):
        # 使用 LLM 解析的详细信息
        name = character_detail.get("name", subject)

        # 年龄
        age = _translate_and_clean(character_detail.get("age", ""))
        if age:
            age_prompts = {
                "child": "child, 6-12 years old, youthful",
                "teenage": "teenage, 14-18 years old",
                "young adult": "young adult, 20-30 years old",
                "middle-aged": "middle-aged, 40-50 years old, experienced",
                "elderly": "elderly, 60-70 years old, wise"
            }
            for key, prompt in age_prompts.items():
                if key in age.lower():
                    parts.append(prompt)
                    break

        # 外貌特征（翻译 + 清理）
        appearance = _translate_and_clean(character_detail.get("appearance", ""))
        if appearance:
            parts.append(appearance)
        else:
            # 默认外貌描述
            if "狐" in name:
                parts.append("beautiful white fox with fluffy white fur, bright intelligent eyes")
            elif "樵夫" in name or "woodcutter" in name.lower():
                parts.append("weathered face, kind eyes, rough hands, honest expression")
            elif "男孩" in name:
                parts.append("young boy, curious expression, bright eyes")
            elif "女孩" in name:
                parts.append("young girl, innocent smile, bright eyes")

        # 服装（翻译 + 清理）
        clothing = _translate_and_clean(character_detail.get("clothing", ""))
        if clothing:
            parts.append(clothing)
        else:
            # 根据场景/季节推断服装
            scene = parsed.get("scene", "").lower()
            if "雪" in scene or "冬" in scene:
                if "樵夫" in name or "woodcutter" in name.lower():
                    parts.append("thick cotton padded winter clothes, worn but warm, traditional Chinese rural style")
                else:
                    parts.append("warm winter clothing with thick padding")
            elif "古" in scene or "古代" in description:
                parts.append("traditional Chinese ancient clothing, Hanfu style")

        # 配饰（翻译 + 清理）
        # 定妆照需要排除包含动作的配饰
        accessories = _translate_and_clean(character_detail.get("accessories", ""))
        if accessories and include_pose:
            parts.append(accessories)
        elif accessories and not include_pose:
            # 定妆照：过滤掉包含动作的配饰
            action_words = ["holding", "running", "chasing", "walking", "running", "running after", "leash", "running alongside"]
            is_action = any(word in accessories.lower() for word in action_words)
            if not is_action:
                parts.append(accessories)
        else:
            # 默认配饰
            if "樵夫" in name or "woodcutter" in name.lower():
                parts.append("bamboo hat, carrying basket on back")

        # 姿态（仅在需要时添加，定妆照应排除）
        if include_pose:
            pose = _translate_and_clean(character_detail.get("pose", ""))
            if pose:
                parts.append(pose)

    else:
        # 回退到模板
        if subject in CHARACTER_TEMPLATES:
            template = CHARACTER_TEMPLATES[subject]
            parts.append(template.get("anchor", ""))
            if template.get("appearance"):
                parts.append(template["appearance"])
            if template.get("clothing"):
                parts.append(template["clothing"])
            if template.get("accessories"):
                parts.append(template["accessories"])
        else:
            # 未知角色
            parts.append(f"A {subject}")

    # ========== 3. 添加场景 ==========
    if include_scene:
        scene = parsed.get("scene", "")
        if scene:
            parts.append(scene)
        else:
            parts.append("natural outdoor setting, soft lighting, peaceful atmosphere")

    # ========== 4. 添加物品 ==========
    if include_objects:
        objects = parsed.get("objects", [])
        for obj in objects:
            if isinstance(obj, dict):
                desc = _translate_and_clean(obj.get("description", ""))
                name = _translate_and_clean(obj.get("name", ""))
                if desc:
                    parts.append(desc)
                elif name:
                    parts.append(name)
            elif isinstance(obj, str):
                cleaned = _translate_and_clean(obj)
                if cleaned:
                    parts.append(cleaned)

    # ========== 5. 添加艺术风格 ==========
    if include_style and parsed.get("style"):
        style_prompt = parsed["style"].get("prompt", "")
        if style_prompt:
            parts.append(style_prompt)
    elif subject in CHARACTER_TEMPLATES:
        template = CHARACTER_TEMPLATES[subject]
        if "style" in template:
            parts.append(template["style"])

    # ========== 6. 添加情绪 ==========
    mood = parsed.get("mood", "")
    if mood:
        mood_prompts = {
            "happy": "happy atmosphere, bright lighting, warm tones",
            "sad": "sad atmosphere, muted colors, melancholic mood",
            "mysterious": "mysterious atmosphere, dramatic shadows, intrigue",
            "warm": "warm atmosphere, golden hour light, cozy feeling",
            "touching": "emotional atmosphere, poignant moment, touching scene",
            "tense": "tense atmosphere, dramatic lighting, suspense",
            "温馨": "warm and touching atmosphere, golden lighting, emotional",
            "神秘": "mysterious atmosphere, dramatic lighting, ethereal",
            "感人": "touching and emotional, poignant moment, heartfelt"
        }
        mood_lower = mood.lower() if isinstance(mood, str) else str(mood)
        for key, prompt in mood_prompts.items():
            if key in mood_lower:
                parts.append(prompt)
                break

    # ========== 7. 过滤空元素并翻译后返回 ==========
    translated_parts = []
    for p in parts:
        if p:
            cleaned = _translate_and_clean(p)
            if cleaned:
                translated_parts.append(cleaned)

    return ", ".join(translated_parts)


def build_negative_prompt(parsed: dict) -> str:
    """构建负面提示词"""
    negatives = [
        "low quality", "blurry", "distorted", "ugly", "bad anatomy",
        "extra fingers", "watermark", "text", "logo", "signature"
    ]
    if parsed.get("style") and parsed["style"].get("negative"):
        negatives.append(parsed["style"]["negative"])
    return ", ".join(negatives)


# 故事分镜模板
STORY_SHOTS = {
    "相遇": [
        {"type": "establishing", "name": "环境建立",
         "content": "establishing the forest environment, boy walking along a mossy path, discovering tracks",
         "style": "cinematic wide shot, ethereal forest lighting, mysterious atmosphere",
         "camera": "slow tracking shot, establishing view"},
        {"type": "discovery", "name": "发现",
         "content": "boy notices a white fox watching from behind trees, eyes meeting, moment of surprise",
         "style": "medium shot, golden hour light filtering through leaves, warm tones",
         "camera": "slow push-in, focusing on fox's eyes"},
        {"type": "approach", "name": "靠近",
         "content": "boy slowly crouches down, opens backpack carefully, takes out roasted duck",
         "style": "close-up on hands opening backpack, detail shot, soft bokeh background",
         "camera": "macro detail shot, shallow depth of field"},
        {"type": "offering", "name": "赠送",
         "content": "boy gently places the duck on the ground, sliding it toward the fox, kind gesture",
         "style": "medium shot from fox's perspective, eye-level view, gentle and hopeful mood",
         "camera": "slow pan to follow the food"},
        {"type": "acceptance", "name": "接受",
         "content": "fox approaches cautiously, sniffs the food, then looks at boy with gratitude",
         "style": "close-up on fox face, spark of connection, soft magical glow",
         "camera": "slow zoom in on eyes"},
        {"type": "bonding", "name": "建立友谊",
         "content": "boy and fox sit together peacefully, fox eats the duck happily, boy smiles",
         "style": "warm golden lighting, cozy atmosphere, heartwarming scene",
         "camera": "two-shot, boy and fox together"}
    ],
    "默认": [
        {"type": "open", "name": "开场",
         "content": "wide establishing shot, introduction of main character in setting",
         "style": "cinematic wide, establishing mood, atmospheric lighting"},
        {"type": "action1", "name": "动作1",
         "content": "character performing key action, medium shot",
         "style": "dynamic medium shot, focused composition"},
        {"type": "detail", "name": "细节",
         "content": "close-up detail shot of important object or expression",
         "style": "close-up, shallow depth, bokeh background"},
        {"type": "action2", "name": "动作2",
         "content": "continuation of action, reaction shot",
         "style": "medium shot, emotional lighting"},
        {"type": "climax", "name": "高潮",
         "content": "key moment of the scene, most dramatic composition",
         "style": "dramatic lighting, cinematic composition, heightened emotion"},
        {"type": "ending", "name": "结尾",
         "content": "conclusion shot, peaceful resolution or cliffhanger",
         "style": "soft lighting, reflective mood, slow camera"}
    ]
}


def _generate_custom_shots(
    subjects: list,
    actions: list,
    objects: list,
    scene: str,
    num_shots: int = 3
) -> list:
    """根据实际故事动作生成定制分镜"""
    if not subjects and not actions:
        return []

    main_char = subjects[0] if subjects else "character"
    scene_kw = "snowy landscape" if "snow" in scene.lower() else (scene[:40] if scene else "outdoor setting")

    obj_names = []
    for obj in objects:
        if isinstance(obj, dict):
            n = obj.get("name", "")
            if n:
                obj_names.append(n)
        elif isinstance(obj, str):
            obj_names.append(obj)

    action_map = {
        "蹲下": "kneeling down",
        "走进": "walking into scene",
        "掏出": "taking out from bag",
        "放在": "placing down",
        "躺": "lying",
        "看": "looking at",
        "吃": "eating"
    }

    shots = []

    if len(subjects) >= 2:
        # 多角色故事 - 使用实际角色名
        humans = [s for s in subjects if any(kw in s for kw in ["学生", "男孩", "女孩", "男人", "女人", "樵夫", "农夫", "人", "xi"])]
        animals = [s for s in subjects if s not in humans]

        main_char = humans[0] if humans else subjects[0]
        secondary_char = animals[0] if animals else (subjects[1] if len(subjects) > 1 else subjects[0])

        # 简化角色名（去掉拼音）
        main_simple = main_char.split('(')[0].strip()
        sec_simple = secondary_char.split('(')[0].strip()

        # 分镜1: 主要角色（人）出现
        shots.append({
            "type": "establishing", "name": f"{main_simple}出现",
            "content": f"character in {scene_kw}",
            "style": "wide shot, cinematic"
        })

        # 分镜2: 次要角色（动物）出现
        shots.append({
            "type": "discovery", "name": f"{sec_simple}出现",
            "content": f"animal in {scene_kw}",
            "style": "medium shot"
        })

        # 分镜3: 主要动作
        action_found = False
        for a in actions:
            kw = a.get("keyword", "") if isinstance(a, dict) else str(a)
            if any(x in kw for x in ["牵", "追赶", "跑", "追", "蹲", "掏", "放"]):
                shots.append({
                    "type": "action", "name": "主要动作",
                    "content": f"character {kw}",
                    "style": "close-up, dynamic"
                })
                action_found = True
                break
        if not action_found:
            shots.append({
                "type": "action", "name": "主要动作",
                "content": f"character in action",
                "style": "medium shot"
            })

        # 分镜4: 物品细节（如果有）
        if obj_names:
            shots.append({
                "type": "detail", "name": "物品细节",
                "content": f"detail of {obj_names[0]}",
                "style": "macro detail"
            })
    else:
        shots.append({"type": "open", "name": "开场",
                      "content": f"character in {scene_kw}", "style": "wide establishing"})
        for a in actions[:2]:
            kw = a.get("keyword", "") if isinstance(a, dict) else str(a)
            shots.append({"type": "action", "name": "动作",
                          "content": f"character {kw}", "style": "medium shot"})

    while len(shots) < num_shots:
        shots.append(shots[-1])

    return shots[:num_shots]


def generate_story_shots(
    description: str,
    parsed: dict,
    num_shots: int = 3,
    costume_info: dict = None
) -> list:
    """根据故事内容生成不同的分镜序列"""
    subjects = parsed.get("subjects", ["小男孩"])
    objects = parsed.get("objects", [])
    scene = parsed.get("scene", "")
    style = parsed.get("style", {})
    mood = parsed.get("mood", "gentle")
    actions = parsed.get("actions", [])

    main_subject = subjects[0] if subjects else "小男孩"

    # 构建每个角色的定妆照提示词（只包含角色特征，不含动作）
    # 优先使用传入的 costume_info（定妆照提示词），否则从 parsed 构建
    costume_prompts = {}

    # 如果传入了 costume_info，使用其中的提示词
    if costume_info and costume_info.get('selected'):
        # costume_info['selected'] 是 dict: {subject: {'filepath': ..., 'prompt': ...}}
        selected = costume_info['selected']
        for subj, info in selected.items():
            if isinstance(info, dict) and info.get('prompt'):
                # 从定妆照提示词中提取角色特征（只取前100字符作为基础）
                prompt = info.get('prompt', '')
                base = prompt[:100].rsplit(',', 1)[0] if ',' in prompt[:100] else prompt[:100]
                costume_prompts[subj] = base
            elif isinstance(info, str):
                costume_prompts[subj] = info[:100]

    # 如果 costume_info 为空或没有匹配，从 parsed 构建
    if not costume_prompts:
        for subj in subjects:
            # 从 subjects_detail 中找匹配项
            detail = None
            for d in parsed.get('subjects_detail', []):
                d_name = d.get('name', '')
                # 支持多种匹配方式：纯中文、带拼音后缀、模糊匹配
                clean_name = d_name.split('(')[0].strip()
                if (clean_name == subj or d_name == subj or subj in d_name or
                    clean_name in subj or subj in clean_name):
                    detail = d
                    break

            if detail:
                parts = []
                age = detail.get('age', '')
                appearance = _translate_and_clean(detail.get('appearance', ''))
                clothing = _translate_and_clean(detail.get('clothing', ''))
                accessories = _translate_and_clean(detail.get('accessories', ''))
                for p in [age, appearance, clothing, accessories]:
                    if p:
                        parts.append(p)
                costume_prompts[subj] = ", ".join(parts)
            else:
                costume_prompts[subj] = subj

    # 确定主角
    main_subject = subjects[0] if subjects else "小男孩"

    # 构建物品描述
    object_names = []
    object_descs = []
    for obj in objects:
        if isinstance(obj, dict):
            name = obj.get("name", "")
            desc = obj.get("description", "")
            if name:
                object_names.append(name)
            if desc:
                object_descs.append(desc)
        elif isinstance(obj, str):
            object_names.append(obj)

    scene_desc = _translate_and_clean(scene) if scene else ""
    style_prompt = style.get("prompt", "") if style else ""

    # ========== 提取动作 ==========
    # 如果 LLM 没有提取动作，从描述中直接提取
    actions = parsed.get("actions", [])
    if not actions:
        # 直接从描述中提取动作关键词
        action_keywords = {
            "蹲下": "kneeling down",
            "蹲": "kneeling down",
            "走进": "walking into scene",
            "走进以后": "walking into scene",
            "掏出": "taking out from bag",
            "拿出": "taking out",
            "放在": "placing down",
            "放": "placing",
            "躺": "lying in snow",
            "躺在": "lying in snow",
            "看": "looking at",
            "吃": "eating",
            "相遇": "meeting",
            "遇见": "encountering"
        }
        desc_for_action = description
        for kw, en_desc in action_keywords.items():
            if kw in desc_for_action:
                actions.append({"keyword": kw, "description": en_desc})

    custom_shots = _generate_custom_shots(
        subjects=subjects,
        actions=actions,
        objects=objects,
        scene=scene_desc,
        num_shots=num_shots
    )

    # 确定每个分镜对应的角色
    # 根据故事中的实际角色和动作分配
    shot_char_mapping = []
    if len(subjects) >= 2:
        # 找出主要角色（人）和次要角色（动物/物品）
        humans = [s for s in subjects if any(kw in s for kw in ["学生", "男孩", "女孩", "男人", "女人", "樵夫", "农夫", "人"])]
        animals = [s for s in subjects if s not in humans]

        main_char = humans[0] if humans else subjects[0]
        secondary = animals[0] if animals else (subjects[1] if len(subjects) > 1 else subjects[0])

        for i in range(num_shots):
            if i == 0:
                shot_char_mapping.append(main_char)  # 分镜1: 主要角色
            elif i == 1:
                shot_char_mapping.append(secondary)  # 分镜2: 次要角色
            elif i >= 2:
                shot_char_mapping.append(main_char)  # 后续: 主要角色动作
    else:
        for i in range(num_shots):
            shot_char_mapping.append(subjects[0])

    shots = []
    for i in range(num_shots):
        if custom_shots and i < len(custom_shots):
            tmpl = custom_shots[i]
        else:
            default_idx = i % len(STORY_SHOTS["默认"])
            tmpl = STORY_SHOTS["默认"][default_idx]

        prompt_parts = []

        # 使用当前分镜对应角色的定妆照提示词
        char_for_shot = shot_char_mapping[i] if i < len(shot_char_mapping) else main_subject

        # 尝试多种方式匹配角色名
        char_costume = costume_prompts.get(char_for_shot, "")
        if not char_costume:
            # 尝试从 costume_prompts 中找匹配的键
            for key in costume_prompts:
                if char_for_shot in key or key in char_for_shot:
                    char_costume = costume_prompts[key]
                    break
                # 也尝试去掉拼音后缀后匹配
                clean_key = key.split('(')[0].strip()
                if clean_key == char_for_shot:
                    char_costume = costume_prompts[key]
                    break

        if char_costume:
            base = char_costume[:100].rsplit(',', 1)[0]
            prompt_parts.append(base)
        else:
            prompt_parts.append(costume_prompts.get(main_subject, "")[:100] if main_subject in costume_prompts else "")

        shot_content = tmpl.get("content", "")
        if shot_content:
            prompt_parts.append(shot_content)

        # 添加风格（如果存在）
        if style_prompt:
            prompt_parts.append(style_prompt)

        if object_descs and tmpl.get("type") in ["action", "detail", "approach"]:
            for obj_desc in object_descs[:1]:
                if obj_desc and len(obj_desc) > 3:
                    prompt_parts.append(obj_desc[:60])

        final_prompt = ", ".join([p for p in prompt_parts if p])

        shots.append({
            "shot_num": i + 1,
            "shot_type": tmpl.get("type", ""),
            "name": tmpl.get("name", ""),
            "prompt": final_prompt,
            "style": tmpl.get("style", ""),
            "seed_offset": i,
            "character": char_for_shot,  # 当前分镜对应的角色
            "character_desc": costume_prompts.get(char_for_shot, ""),
            "objects": object_names
        })

    return shots


def generate_video_prompt(
    subject: str,
    parsed: dict,
    shot_num: int,
    shot_type: str
) -> str:
    """生成分镜视频提示词"""
    template = CHARACTER_TEMPLATES.get(subject, {})
    
    # 物品
    objects_desc = []
    if parsed.get("objects"):
        for obj in parsed["objects"]:
            objects_desc.append(obj["description"])
    
    # 基于分镜类型生成动作
    action_map = {
        "establishing": "slowly turning head to look at each other, standing in forest setting",
        "action": "slowly opening backpack, taking out roasted duck, offering with gentle hand gesture",
        "reaction": "fox slowly approaching, sniffing the food, eyes showing curiosity and gratitude",
        "interaction": "gently interacting, boy and fox in harmony, soft natural movements",
        "ending": "slowly walking together, peaceful atmosphere, looking at each other with contentment"
    }
    
    action = action_map.get(shot_type, "gentle slow movement")
    
    # 构建提示词
    parts = []
    parts.append(action)
    
    if objects_desc:
        parts.append(f"with {objects_desc[0]} visible")
    
    parts.append("camera slowly moving, cinematic, soft natural lighting")
    
    mood_map = {
        "gentle": "warm gentle atmosphere",
        "happy": "bright cheerful atmosphere", 
        "mysterious": "ethereal mysterious atmosphere",
        "sad": "melancholic soft atmosphere"
    }
    parts.append(mood_map.get(parsed.get("mood", "gentle"), "gentle atmosphere"))
    
    return ", ".join(parts)

# ============ ComfyUI API ============

def submit_workflow(workflow: dict) -> str:
    """提交工作流到 ComfyUI"""
    response = requests.post(
        f"{COMFYUI_URL}/prompt",
        json={"prompt": workflow},
        timeout=30
    )
    if response.status_code != 200:
        raise RuntimeError(f"工作流提交失败: {response.status_code} - {response.text}")
    return response.json().get("prompt_id")

def wait_for_completion(prompt_id: str, timeout: int = 600) -> dict:
    """等待工作流完成"""
    start_time = time.time()
    last_status = ""
    
    while time.time() - start_time < timeout:
        time.sleep(3)
        try:
            response = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10)
            data = response.json()
        except:
            continue
        
        if prompt_id in data:
            status = data[prompt_id].get("status", {})
            if status.get("completed"):
                return data[prompt_id]
            elif status.get("errored"):
                error_msg = status.get("error", "Unknown error")
                raise RuntimeError(f"工作流出错: {error_msg}")
            
            # 显示进度
            current_status = status.get("status_str", "processing")
            if current_status != last_status:
                print(f"  [{current_status}]")
                last_status = current_status
        
        elapsed = int(time.time() - start_time)
        print(f"  ...处理中 ({elapsed}s)")
    
    raise TimeoutError("工作流执行超时")

def get_workflow_outputs(prompt_id: str) -> list:
    """获取工作流输出文件"""
    response = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10)
    data = response.json()
    
    if prompt_id not in data:
        return []
    
    outputs = []
    for node_id, output in data[prompt_id].get("outputs", {}).items():
        # Wan2.2 I2V 视频输出在 images 字段中（包含 .mp4 文件）
        if "images" in output:
            for img in output["images"]:
                filename = img["filename"]
                # 检查是否是视频文件
                if filename.endswith(".mp4"):
                    outputs.append({
                        "node_id": node_id,
                        "filename": filename,
                        "subfolder": img.get("subfolder", ""),
                        "type": "video"
                    })
                else:
                    outputs.append({
                        "node_id": node_id,
                        "filename": filename,
                        "subfolder": img.get("subfolder", ""),
                        "type": "image"
                    })
    
    return outputs

def download_file(filename: str, subfolder: str = "", output_dir: Path = None) -> Path:
    """下载 ComfyUI 输出的文件"""
    # ComfyUI 文件实际在 COMFYUI_OUTPUT_DIR 下
    if output_dir is None:
        output_dir = COMFYUI_OUTPUT_DIR

    url = f"{COMFYUI_URL}/view"
    params = {"filename": filename}
    if subfolder:
        params["subfolder"] = subfolder

    response = requests.get(url, params=params, timeout=60)

    if response.status_code != 200:
        raise RuntimeError(f"文件下载失败: {filename} (subfolder: {subfolder})")

    # 直接保存到 output_dir / filename，不保留 subfolder 结构避免嵌套
    filepath = output_dir / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "wb") as f:
        f.write(response.content)

    return filepath

# ============ 图像生成 ============

def generate_costume_photos(
    subject: str,
    description: str,
    project_dir: Path,
    num_variants: int = 3,
    parsed: dict = None
) -> list:
    """生成角色定妆照（多种子尝试）"""
    print(f"\n📸 生成定妆照: {subject}")
    print(f"   描述: {description}")
    print(f"   将生成 {num_variants} 种变体供选择\n")
    
    if parsed is None:
        parsed = parse_description(description)
    
    # 加载工作流
    with open(TXT2IMG_WORKFLOW, "r", encoding="utf-8") as f:
        workflow = json.load(f)
    
    # 构建提示词（定妆照排除动作/姿态/场景/物品，只保留角色特征+风格）
    image_prompt = build_character_prompt(subject, description, parsed, include_pose=False, include_scene=False, include_objects=False)

    # 使用动态负面提示词
    negative_prompt = build_negative_prompt(parsed)
    
    # 修改工作流 - 使用简单文件名避免路径重复
    workflow["57:27"]["inputs"]["text"] = image_prompt
    workflow["57:33"]["inputs"]["text"] = negative_prompt
    workflow["9"]["inputs"]["filename_prefix"] = f"costume_{project_dir.name[:8]}"
    
    results = []
    seeds = [generate_seed() for _ in range(num_variants)]
    
    for i, seed in enumerate(seeds):
        print(f"\n  ──────────────────────────────")
        print(f"  变体 {i+1}/{num_variants} (seed: {seed})")
        print(f"  ──────────────────────────────")
        
        # 设置种子
        workflow["57:3"]["inputs"]["seed"] = seed
        
        # 提交
        prompt_id = submit_workflow(workflow)
        
        # 等待
        status = wait_for_completion(prompt_id)
        
        # 下载（直接下载到 COMFYUI_OUTPUT_DIR）
        outputs = get_workflow_outputs(prompt_id)
        for output in outputs:
            if output["type"] == "image":
                filepath = download_file(
                    output["filename"],
                    output.get("subfolder", ""),
                    COMFYUI_OUTPUT_DIR
                )
                results.append({
                    "seed": seed,
                    "filepath": str(filepath),
                    "prompt_id": prompt_id,
                    "prompt": image_prompt
                })
                print(f"  ✅ 保存: {filepath.name}")
    
    return results

def generate_storyboard_images(
    project_dir: Path,
    shots: list,
    base_seed: int
) -> list:
    """生成分镜图（保持角色一致性）"""
    print(f"\n🖼️ 生成分镜图 ({len(shots)} 个场景)")
    
    # 加载工作流
    with open(TXT2IMG_WORKFLOW, "r", encoding="utf-8") as f:
        workflow = json.load(f)
    
    # 预设负面提示词
    negative_prompt = "low quality, blurry, distorted, ugly, bad anatomy, extra fingers, watermark, text"
    workflow["57:33"]["inputs"]["text"] = negative_prompt
    
    results = []
    
    for i, shot_info in enumerate(shots):
        shot_num = shot_info["shot_num"]
        prompt = shot_info["prompt"]
        
        print(f"\n  ──────────────────────────────")
        print(f"  分镜 {shot_num}/{len(shots)}: {shot_info.get('name', '')}")
        print(f"  ──────────────────────────────")
        print(f"  提示词: {prompt[:60]}...")
        
        # 计算序列 seed（保持一致性）
        frame_seed = base_seed + i * 100
        
        # 修改工作流 - 使用简单文件名避免路径重复
        workflow["57:27"]["inputs"]["text"] = prompt
        workflow["57:3"]["inputs"]["seed"] = frame_seed
        workflow["9"]["inputs"]["filename_prefix"] = f"sb_{project_dir.name[:8]}_{shot_num:02d}"
        
        # 提交
        prompt_id = submit_workflow(workflow)
        
        # 等待
        wait_for_completion(prompt_id)
        
        # 下载（直接下载到 COMFYUI_OUTPUT_DIR，使用 ComfyUI 返回的 subfolder 保持目录结构）
        outputs = get_workflow_outputs(prompt_id)
        for output in outputs:
            if output["type"] == "image":
                # 使用 ComfyUI 的 subfolder 路径，下载到 COMFYUI_OUTPUT_DIR
                filepath = download_file(
                    output["filename"],
                    output.get("subfolder", ""),
                    COMFYUI_OUTPUT_DIR  # 直接下载到 ComfyUI output 目录
                )
                results.append({
                    "shot_num": shot_num,
                    "shot_type": shot_info.get("shot_type", ""),
                    "name": shot_info.get("name", ""),
                    "prompt": prompt,
                    "seed": frame_seed,
                    "filepath": str(filepath)
                })
                print(f"  ✅ {filepath.name}")
    
    return results

# ============ 视频生成 ============

def generate_video_from_image(
    image_path: str,
    video_prompt: str,
    project_dir: Path,
    shot_name: str,
    seed: int = None,
    reference_image: str = None  # 定妆照路径，用于角色一致性
) -> str:
    """从图像生成视频
    
    Args:
        reference_image: 定妆照路径，使用 CLIP Vision 参考保持角色一致性
    """
    print(f"\n  🎬 生成视频: {shot_name}")
    if reference_image:
        print(f"  📸 参考定妆照: {Path(reference_image).name}")
    
    # 选择工作流模板（有参考图时使用带 CLIP Vision 的工作流）
    if reference_image:
        workflow_template = I2V_WORKFLOW_REFERENCE
        print(f"  ⚙️ 使用: CLIP Vision 参考工作流")
    else:
        workflow_template = I2V_WORKFLOW_TEMPLATE
        print(f"  ⚙️ 使用: 原始 I2V 工作流")
    
    # 加载工作流模板
    with open(workflow_template, "r", encoding="utf-8") as f:
        workflow = json.load(f)
    
    # 获取图像文件名
    image_path_obj = Path(image_path)
    image_name = image_path_obj.name
    
    # 将图片复制到 ComfyUI input 目录
    import shutil
    comfyui_input_path = COMFYUI_INPUT_DIR / image_name
    shutil.copy(image_path, comfyui_input_path)
    print(f"  📁 已复制图片到: {comfyui_input_path}")
    
    # 修改图像路径（LoadImage 使用 input 目录中的文件名）
    workflow["97"]["inputs"]["image"] = image_name
    
    # 如果有参考图，添加到工作流
    if reference_image:
        ref_name = Path(reference_image).name
        ref_input_path = COMFYUI_INPUT_DIR / ref_name
        shutil.copy(reference_image, ref_input_path)
        workflow["200:11"]["inputs"]["image"] = ref_name  # CLIP Vision LoadImage
    
    # 修改提示词
    workflow["129:93"]["inputs"]["text"] = video_prompt
    
    # 负面提示词
    negative_prompt = "色调艳丽，过曝，静态，细节模糊，字幕，风格作品画作，画面静止，最差质量，低质量，JPEG残留，丑陋，残缺，多余手指"
    workflow["129:89"]["inputs"]["text"] = negative_prompt
    
    # 修改输出路径 - 使用简单文件名避免路径重复
    workflow["108"]["inputs"]["filename_prefix"] = f"vid_{project_dir.name[:8]}_{shot_name}"
    
    # 设置种子
    if seed is None:
        seed = generate_seed()
    
    # 两个采样器使用相同种子
    workflow["129:86"]["inputs"]["noise_seed"] = seed
    workflow["129:85"]["inputs"]["noise_seed"] = seed
    
    print(f"  提示词: {video_prompt[:50]}...")
    print(f"  种子: {seed}")
    
    # 提交
    prompt_id = submit_workflow(workflow)
    print(f"  Prompt ID: {prompt_id[:8]}...")
    
    # 等待
    wait_for_completion(prompt_id, timeout=900)
    
    # 下载（通过 /view API 从 ComfyUI 真实下载到本地缓存）
    outputs = get_workflow_outputs(prompt_id)
    for output in outputs:
        if output["type"] == "video":
            video_path = download_file(output["filename"], output.get("subfolder", ""))
            # 归档到项目 videos 目录
            videos_dir = project_dir / "videos"
            videos_dir.mkdir(parents=True, exist_ok=True)
            dest = videos_dir / output["filename"]
            shutil.copy2(str(video_path), str(dest))
            print(f"  ✅ 视频路径: {dest}")
            return str(dest)

    return None

# ============ TTS & 合成 ============

def synthesize_tts(text: str, output_path: Path) -> str:
    """合成 TTS 语音"""
    print(f"\n🎤 合成语音...")
    print(f"   文本: {text[:50]}...")
    
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
    
    try:
        response = requests.post(FISH_SPEECH_API, json=payload, timeout=300)
        
        if response.status_code != 200:
            raise RuntimeError(f"TTS 失败: {response.status_code}")
        
        with open(output_path, "wb") as f:
            f.write(response.content)
        
        print(f"  ✅ 音频保存: {output_path.name}")
        return str(output_path)
    except Exception as e:
        print(f"  ⚠️ TTS 失败: {e}")
        print(f"  跳过音频合成")
        return None

def merge_video_audio(video_path: str, audio_path: str, output_path: Path) -> bool:
    """合并音视频"""
    print(f"\n🔧 合并音视频...")
    
    if not audio_path or not Path(audio_path).exists():
        print("  ⚠️ 音频文件不存在，跳过合并")
        # 直接复制视频
        shutil.copy2(video_path, str(output_path))
        return True
    
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-map", "0:v:0", "-map", "1:a:0",
        str(output_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"  ⚠️ FFmpeg 失败: {result.stderr[:200]}")
        # 复制视频作为备选
        shutil.copy2(video_path, str(output_path))
        return False
    
    print(f"  ✅ 合并完成: {output_path.name}")
    return True

def concatenate_videos(video_paths: list, output_path: Path) -> bool:
    """拼接多个视频"""
    print(f"\n🎞️ 拼接 {len(video_paths)} 个视频...")
    
    if not video_paths:
        return False
    
    # 创建临时文件列表
    list_file = output_path.parent / "concat_list.txt"
    with open(list_file, "w") as f:
        for path in video_paths:
            f.write(f"file '{path}'\n")
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    list_file.unlink()
    
    if result.returncode != 0:
        print(f"  ⚠️ 拼接失败: {result.stderr[:200]}")
        return False
    
    print(f"  ✅ 拼接完成: {output_path.name}")
    return True

# ============ 交互式选择 ============

def select_costume_photo(costume_results: list, auto_select: bool = False) -> dict:
    """交互式选择定妆照"""
    print("\n" + "="*60)
    print("📸 定妆照生成完成，请选择满意的版本")
    print("="*60)
    
    for i, result in enumerate(costume_results):
        filepath = Path(result["filepath"])
        print(f"\n  [{i+1}] {filepath.name}")
        print(f"      Seed: {result['seed']}")
        print(f"      路径: {filepath}")
    
    # 非交互模式：自动选择第一张
    if auto_select:
        print("\n  [自动选择第1张]")
        return costume_results[0]
    
    print(f"\n  [r] 重新生成更多变体")
    print(f"  [q] 退出")
    
    while True:
        try:
            choice = input("\n请选择 (1-3, r, q): ").strip()
        except EOFError:
            print("\n  [自动选择第1张]")
            return costume_results[0]
        
        if choice.lower() == 'q':
            sys.exit(0)
        elif choice.lower() == 'r':
            return None  # 表示重新生成
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(costume_results):
                return costume_results[idx]
        except:
            pass
        
        print("无效选择，请重试")

def select_storyboard_images(storyboard_results: list, num_to_select: int = None, auto_select: bool = False) -> list:
    """交互式选择分镜图"""
    print("\n" + "="*60)
    print("🖼️ 分镜图生成完成，请选择要制作视频的镜头")
    print("="*60)
    
    if num_to_select is None:
        num_to_select = len(storyboard_results)
    
    for i, result in enumerate(storyboard_results):
        filepath = Path(result["filepath"])
        print(f"\n  [{i+1}] 分镜 {result['shot_num']}: {filepath.name}")
        print(f"      提示词: {result['prompt'][:50]}...")
    
    # 非交互模式：自动全部选择
    if auto_select:
        print(f"\n  [自动选择全部 {len(storyboard_results)} 个分镜]")
        return storyboard_results
    
    print(f"\n格式: 1,2,3 或 1-3 或 all (默认全部)")
    
    while True:
        try:
            choice = input(f"\n请选择要制作视频的镜头 (默认 all): ").strip()
        except EOFError:
            print(f"\n  [自动选择全部]")
            return storyboard_results
        
        if choice.lower() in ['q', 'quit', 'exit']:
            sys.exit(0)
        elif choice.lower() in ['', 'all']:
            return storyboard_results
        
        # 解析选择
        selected = []
        try:
            # 处理 "1,2,3" 或 "1-3" 格式
            if '-' in choice:
                parts = choice.split('-')
                start = int(parts[0]) - 1
                end = int(parts[1])
                selected = storyboard_results[start:end]
            elif ',' in choice:
                indices = [int(x.strip()) - 1 for x in choice.split(',')]
                selected = [storyboard_results[i] for i in indices if 0 <= i < len(storyboard_results)]
            else:
                idx = int(choice) - 1
                if 0 <= idx < len(storyboard_results):
                    selected = [storyboard_results[idx]]
            
            if selected:
                return selected
        except:
            pass
        
        print("无效选择，请重试")

# ============ 主流水线 ============

def run_costume_generation(description: str, num_variants: int = 3) -> dict:
    """仅生成定妆照阶段"""
    project_name = f"costume_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    project_dir = create_project_dir(project_name)
    
    print("="*60)
    print("📸 定妆照生成模式")
    print("="*60)
    print(f"\n描述: {description}")
    
    # 检查
    if not check_comfyui():
        print("\n❌ ComfyUI 未运行")
        return None
    
    # 解析
    parsed = parse_description(description)
    main_subject = parsed["subjects"][0]
    
    print(f"识别角色: {main_subject}")
    
    # 生成
    results = generate_costume_photos(
        subject=main_subject,
        description=description,
        project_dir=project_dir,
        num_variants=num_variants,
        parsed=parsed
    )
    
    # 选择（非交互模式自动选择第一张）
    selected = select_costume_photo(results, auto_select=True)
    
    if selected is None:
        print("\n🔄 重新生成更多变体...")
        return run_costume_generation(description, num_variants + 2)
    
    return {
        "project_dir": project_dir,
        "selected": selected,
        "all_results": results
    }

def run_full_pipeline(
    description: str,
    tts_text: str = None,
    num_costume_variants: int = 3,
    num_shots: int = 3,
    costume_result: dict = None
):
    """运行完整流水线"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_name = f"project_{timestamp}"
    project_dir = create_project_dir(project_name)
    
    print("="*60)
    print("🎬 短视频生成流水线")
    print("="*60)
    print(f"\n📝 描述: {description}")
    print(f"📁 项目: {project_name}")
    
    # 检查服务
    print("\n🔍 检查服务状态...")
    comfyui_ok = check_comfyui()
    fish_ok = check_fish_speech()
    print(f"   ComfyUI:     {'✅' if comfyui_ok else '❌'}")
    print(f"   Fish Speech: {'✅' if fish_ok else '⚠️ (TTS将跳过)'}")
    
    if not comfyui_ok:
        print(f"\n❌ 请先启动 ComfyUI（http://127.0.0.1:8188 未响应），Windows 下通常为: cd ComfyUI目录 && py main.py")
        return None
    
    # 解析描述
    parsed = parse_description(description)
    print(f"\n📋 解析结果:")
    print(f"   角色: {parsed['subjects']}")
    print(f"   物品: {[o.get('keyword', o.get('name', o)) if isinstance(o, dict) else o for o in parsed.get('objects', [])]}")
    print(f"   动作: {parsed.get('actions', [])}")
    print(f"   场景: {parsed.get('scene', '')[:50]}...")
    print(f"   情绪: {parsed.get('mood', 'gentle')}")
    
    main_subject = parsed["subjects"][0]
    character_anchor = CHARACTER_TEMPLATES.get(main_subject, {}).get("anchor", description)
    
    # ============ Step 1: 定妆照 ============
    if costume_result is None:
        print(f"\n{'='*60}")
        print("📸 Step 1: 生成定妆照")
        print("="*60)
        
        results = generate_costume_photos(
            subject=main_subject,
            description=description,
            project_dir=project_dir,
            num_variants=num_costume_variants,
            parsed=parsed
        )
        
        selected = select_costume_photo(results, auto_select=True)
        if selected is None:
            print("重新生成...")
            return run_full_pipeline(description, tts_text, num_costume_variants + 2, num_shots)
    else:
        selected = costume_result["selected"]
        # 复制选定的定妆照到新项目
        import shutil
        src = Path(selected["filepath"])
        dst = project_dir / "costume_photos" / src.name
        shutil.copy(src, dst)
        selected = {
            "seed": selected["seed"],
            "filepath": str(dst),
            "prompt": selected.get("prompt", description)
        }
        print(f"\n📌 使用已有定妆照: {dst.name}")
    
    base_seed = selected["seed"]
    
    # ============ Step 2: 分镜图 ============
    print(f"\n{'='*60}")
    print("🖼️ Step 2: 生成分镜图")
    print("="*60)
    
    # 生成分镜提示词（每个分镜独特内容+风格）
    # 传入定妆照信息以保持角色一致性
    costume_info = {"selected": selected}
    shots = generate_story_shots(
        description=description,
        parsed=parsed,
        num_shots=num_shots,
        costume_info=costume_info
    )
    
    # 打印提示词预览
    print("\n自动生成的分镜提示词:")
    for s in shots:
        print(f"  [{s['shot_num']}] {s['name']}: {s['prompt'][:60]}...")
        print(f"      风格: {s['style'][:50]}...")
    
    # 生成
    storyboard_results = generate_storyboard_images(
        project_dir=project_dir,
        shots=shots,
        base_seed=base_seed
    )
    
    # 选择（非交互模式自动选择全部）
    selected_shots = select_storyboard_images(storyboard_results, auto_select=True)
    print(f"\n✅ 已选择 {len(selected_shots)} 个分镜进行视频生成")
    
    # ============ Step 3: 视频生成 ============
    print(f"\n{'='*60}")
    print("🎬 Step 3: 生成分镜视频")
    print("="*60)
    
    video_results = []
    for i, sb in enumerate(selected_shots):
        video_prompt = generate_video_prompt(
            subject=main_subject,
            parsed=parsed,
            shot_num=i,
            shot_type=sb.get("shot_type", "action")
        )
        
        video_path = generate_video_from_image(
            image_path=sb["filepath"],
            video_prompt=video_prompt,
            project_dir=project_dir,
            shot_name=f"shot_{sb['shot_num']:02d}",
            seed=base_seed + i * 1000,
            reference_image=selected["filepath"]  # 使用定妆照作为 CLIP Vision 参考
        )
        
        if video_path:
            video_results.append(video_path)
    
    if not video_results:
        print("❌ 视频生成失败")
        return None
    
    print(f"\n✅ 分镜视频生成完成: {len(video_results)} 个")
    
    # ============ Step 4: TTS & 合成 ============
    audio_path = None
    if tts_text:
        print(f"\n{'='*60}")
        print("🎤 Step 4: TTS & 合成短片")
        print("="*60)

        # 按需启动 fish-speech（TTS 完成后释放显存）
        fish_started = start_fish_server()

        # TTS
        audio_file = project_dir / "audio" / "narration.wav"
        audio_path = synthesize_tts(tts_text, audio_file)

        # 拼接视频
        concat_video = project_dir / "video_concat.mp4"
        concatenate_videos(video_results, concat_video)

        # 合并音视频
        output_final = project_dir / "final_short.mp4"
        if audio_path:
            merge_video_audio(str(concat_video), audio_path, output_final)
        else:
            import shutil
            shutil.copy(str(concat_video), str(output_final))

        # 释放显存（本进程启动的实例）
        stop_fish_server()

        print(f"\n🎉 流水线完成!")
        print(f"   最终成品: {output_final}")
    else:
        print(f"\n🎉 视频生成完成!")
        print(f"   视频文件位置: {project_dir / 'videos'}")
        if not tts_text:
            print("   (如需配音，请使用 --tts-text 参数)")
    
    # 生成报告
    report = {
        "project_name": project_name,
        "description": description,
        "tts_text": tts_text,
        "main_subject": main_subject,
        "costume_photo": selected["filepath"],
        "costume_seed": selected["seed"],
        "storyboard_images": [r["filepath"] for r in storyboard_results],
        "selected_shots": [r["filepath"] for r in selected_shots],
        "storyboard_videos": video_results,
        "timestamp": timestamp
    }
    
    report_path = project_dir / "report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📋 完整报告: {report_path}")
    
    return report

# ============ CLI 入口 ============

def main():
    parser = argparse.ArgumentParser(
        description="短视频生成流水线 - 描述 → 定妆照 → 分镜图 → 分镜视频 → 短片",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例: (Windows 用 py，Linux/Mac 用 python)
  # 交互模式
  py main_pipeline.py --interactive
  
  # 一键生成完整短片
  py main_pipeline.py -d "一个小男孩在森林里遇到一只白狐" -t "从前有座山..."
  
  # 仅生成定妆照
  py main_pipeline.py -d "描述" --costume-only
  
  # 指定分镜数量
  py main_pipeline.py -d "描述" -s 5
        """
    )
    
    parser.add_argument("--description", "-d", help="场景描述")
    parser.add_argument("--tts-text", "-t", help="TTS 配音文本")
    parser.add_argument("--costume-variants", "-c", type=int, default=3, help="定妆照变体数 (默认3)")
    parser.add_argument("--shots", "-s", type=int, default=3, help="分镜数量 (默认3)")
    parser.add_argument("--costume-only", action="store_true", help="仅生成定妆照")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互模式")
    
    args = parser.parse_args()
    
    # 交互模式
    if args.interactive:
        print("\n" + "="*60)
        print("🎬 短视频生成交互模式")
        print("="*60)
        print("输入简单描述，系统自动完成提示词补充、图像生成、视频合成")
        print("(输入 q 退出)\n")
        
        while True:
            description = input("\n📝 请输入场景描述: ").strip()
            if description.lower() in ['q', 'quit', 'exit']:
                print("再见!")
                break
            
            if not description:
                continue
            
            # 可选 TTS
            tts_text = input("🎤 TTS配音文本 (直接回车跳过): ").strip()
            
            run_full_pipeline(
                description=description,
                tts_text=tts_text if tts_text else None,
                num_costume_variants=args.costume_variants,
                num_shots=args.shots
            )
        
        return
    
    # 参数检查
    if not args.description:
        parser.print_help()
        print("\n❌ 请提供 --description 参数")
        print("   或使用 --interactive 进入交互模式")
        return
    
    # 仅定妆照模式
    if args.costume_only:
        result = run_costume_generation(args.description, args.costume_variants)
        if result:
            print(f"\n✅ 定妆照已保存到: {result['project_dir'] / 'costume_photos'}")
            print(f"   选中: {Path(result['selected']['filepath']).name}")
        return
    
    # 完整流水线
    run_full_pipeline(
        description=args.description,
        tts_text=args.tts_text,
        num_costume_variants=args.costume_variants,
        num_shots=args.shots
    )

if __name__ == "__main__":
    main()

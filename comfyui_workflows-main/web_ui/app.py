"""
故事视频生成流水线 - Web UI
基于 ComfyUI WanVideo 2.2 I2V

功能:
1. 定妆照生成 (TXT2IMG)
2. 分镜图生成 (TXT2IMG)
3. 分镜视频生成 (I2V with CLIP Vision Reference)
"""

import os
import sys
import json
import random
import string
import shutil
import subprocess
import requests
import threading
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))
import main_pipeline

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# 配置
WORKFLOW_DIR = Path(__file__).parent.parent
PROJECTS_DIR = WORKFLOW_DIR / 'output' / 'web_projects'
COMFYUI_URL = os.environ.get('COMFYUI_URL', 'http://127.0.0.1:8188')
# 与 main_pipeline.py 保持一致：输出为下载缓存目录，输入须为真实 ComfyUI/input
COMFYUI_OUTPUT = Path(os.environ.get('COMFYUI_OUTPUT_DIR', str(WORKFLOW_DIR / 'output' / 'comfyui_downloads')))
COMFYUI_INPUT = Path(os.environ.get('COMFYUI_INPUT_DIR', r'D:\comfy\ComfyUI_windows_portable\ComfyUI\input'))

PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# 辅助函数
# ============================================================================

import re

def random_id(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def get_comfyui_status():
    """检查 ComfyUI 连接状态"""
    try:
        resp = requests.get(f'{COMFYUI_URL}/system_stats', timeout=5)
        return {'status': 'connected', 'info': resp.json()}
    except:
        return {'status': 'disconnected', 'info': None}

def get_queue_status():
    """获取队列状态"""
    try:
        resp = requests.get(f'{COMFYUI_URL}/queue', timeout=5)
        data = resp.json()
        return {
            'running': len(data.get('queue_running', [])),
            'pending': len(data.get('queue_pending', []))
        }
    except:
        return {'running': 0, 'pending': 0}

def find_latest_file(directory, pattern='*', extensions=None):
    """查找最新的文件"""
    dir_path = Path(directory)
    if not dir_path.exists():
        return None
    
    files = []
    for ext in (extensions or ['*']):
        files.extend(dir_path.glob(f'{pattern}.{ext}'))
    
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)

def wait_for_comfyui_output(prompt_id, timeout=600, poll_interval=5):
    """等待 ComfyUI 生成完成"""
    start_time = datetime.now()
    while (datetime.now() - start_time).seconds < timeout:
        try:
            resp = requests.get(f'{COMFYUI_URL}/history/{prompt_id}', timeout=10)
            history = resp.json()
            
            if prompt_id in history:
                status = history[prompt_id].get('status', {})
                if status.get('completed', False):
                    return {'completed': True, 'outputs': history[prompt_id].get('outputs', {})}
                elif status.get('error_str'):
                    return {'completed': False, 'error': status['error_str']}
            
            # 检查是否有新文件生成
            queue = get_queue_status()
            if queue['running'] == 0 and queue['pending'] == 0:
                # 队列空了但没找到历史，可能已完成
                return {'completed': True, 'outputs': {}}
        
        except Exception as e:
            print(f"Poll error: {e}")
        
        import time
        time.sleep(poll_interval)
    
    return {'completed': False, 'error': 'Timeout'}

# ============================================================================
# 模板变量预览
# ============================================================================

def get_template_preview():
    """获取模板变量预览"""
    main_py_path = WORKFLOW_DIR / 'main_pipeline.py'

    # 读取角色模板
    characters = {
        "小男孩": "A young Chinese boy, 8-10 years old, black hair, black eyes...",
        "小女孩": "A young Chinese girl, 8-10 years old, black hair...",
        "白狐": "A beautiful white fox with fluffy white fur...",
        "小男孩和白狐": "A young Chinese boy + A beautiful white fox..."
    }

    # 分镜类型
    shots_preview = [
        {"type": "establishing", "name": "环境建立", "content": "boy walking along mossy path..."},
        {"type": "discovery", "name": "发现", "content": "boy notices white fox watching..."},
        {"type": "approach", "name": "靠近", "content": "boy crouches, opens backpack..."},
        {"type": "offering", "name": "赠送", "content": "boy places duck on ground..."},
        {"type": "acceptance", "name": "接受", "content": "fox approaches, sniffs food..."},
        {"type": "bonding", "name": "建立友谊", "content": "boy and fox sit together..."}
    ]

    return {
        'characters': characters,
        'shots': shots_preview
    }

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """获取系统状态"""
    comfyui = get_comfyui_status()
    queue = get_queue_status()
    return jsonify({
        'comfyui': comfyui,
        'queue': queue
    })

@app.route('/api/templates')
def api_templates():
    """获取模板预览"""
    return jsonify(get_template_preview())

@app.route('/api/parameters')
def api_parameters():
    """获取参数配置"""
    return jsonify({
        'required': {
            'description': {
                'name': 'description',
                'label': '故事描述',
                'type': 'textarea',
                'required': True,
                'placeholder': '例如: 一个男孩在森林里遇到了一只白狐，于是拿出自己背包里的酱板鸭送给了它',
                'help': '描述故事的主要情节，包括主角、场景和关键事件'
            }
        },
        'optional': {
            'num_costumes': {
                'name': 'num_costumes',
                'label': '定妆照数量',
                'type': 'number',
                'default': 3,
                'min': 1,
                'max': 6,
                'help': '生成的定妆照变体数量，用户可选择'
            },
            'num_shots': {
                'name': 'num_shots',
                'label': '分镜数量',
                'type': 'number',
                'default': 3,
                'min': 1,
                'max': 6,
                'help': '分镜图/视频的数量'
            },
            'use_reference': {
                'name': 'use_reference',
                'label': '使用CLIP Vision参考',
                'type': 'checkbox',
                'default': True,
                'help': '使用定妆照作为参考，保持角色一致性'
            },
            'seed': {
                'name': 'seed',
                'label': '随机种子',
                'type': 'number',
                'default': -1,
                'help': '-1 表示随机种子'
            },
            'length': {
                'name': 'length',
                'label': '视频帧数',
                'type': 'number',
                'default': 81,
                'min': 17,
                'max': 161,
                'step': 16,
                'help': '生成视频的帧数 (17-161)'
            },
            'steps': {
                'name': 'steps',
                'label': '采样步数',
                'type': 'number',
                'default': 40,
                'min': 10,
                'max': 100,
                'help': '扩散模型采样步数'
            },
            'cfg': {
                'name': 'cfg',
                'label': 'CFG强度',
                'type': 'number',
                'default': 7.0,
                'min': 1.0,
                'max': 15.0,
                'step': 0.5,
                'help': 'Classifier-Free Guidance 强度'
            }
        },
        'functions': {
            'generate_costume': {
                'name': 'generate_costume',
                'label': '生成定妆照',
                'description': '根据故事描述生成角色定妆照',
                'requires': ['description'],
                'output_type': 'images'
            },
            'generate_storyboard': {
                'name': 'generate_storyboard',
                'label': '生成分镜图',
                'description': '根据故事和定妆照生成分镜图',
                'requires': ['description'],
                'output_type': 'images',
                'note': '需要先有定妆照'
            },
            'generate_videos': {
                'name': 'generate_videos',
                'label': '生成分镜视频',
                'description': '将分镜图转换为视频',
                'requires': ['description'],
                'output_type': 'videos',
                'note': '需要先有分镜图'
            },
            'generate_all': {
                'name': 'generate_all',
                'label': '一键生成全部',
                'description': '执行完整流水线：定妆照 → 分镜图 → 分镜视频',
                'requires': ['description'],
                'output_type': 'all'
            }
        }
    })

@app.route('/api/projects')
def api_projects():
    """获取项目列表"""
    projects = []
    for p_dir in sorted(PROJECTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
        if p_dir.is_dir():
            config_file = p_dir / 'config.json'
            if config_file.exists():
                with open(config_file) as f:
                    config = json.load(f)
                    projects.append({
                        'id': p_dir.name,
                        'name': config.get('name', 'Unnamed'),
                        'description': config.get('description', ''),
                        'created': config.get('created', ''),
                        'status': config.get('status', 'draft')
                    })
    return jsonify(projects)

@app.route('/api/projects', methods=['POST'])
def api_create_project():
    """创建新项目"""
    data = request.json
    project_id = random_id()
    project_dir = PROJECTS_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    
    config = {
        'id': project_id,
        'name': data.get('name', f'Project_{project_id}'),
        'description': data.get('description', ''),
        'created': datetime.now().isoformat(),
        'status': 'draft',
        'params': data.get('params', {}),
        'costumes': [],
        'storyboards': [],
        'videos': []
    }
    
    with open(project_dir / 'config.json', 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    return jsonify({'id': project_id, 'config': config})

@app.route('/api/projects/<project_id>')
def api_get_project(project_id):
    """获取项目详情"""
    project_dir = PROJECTS_DIR / project_id
    config_file = project_dir / 'config.json'
    
    if not config_file.exists():
        return jsonify({'error': 'Project not found'}), 404
    
    with open(config_file) as f:
        config = json.load(f)
    
    return jsonify(config)

@app.route('/api/projects/<project_id>', methods=['PUT'])
def api_update_project(project_id):
    """更新项目"""
    project_dir = PROJECTS_DIR / project_id
    config_file = project_dir / 'config.json'
    
    if not config_file.exists():
        return jsonify({'error': 'Project not found'}), 404
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    data = request.json
    config.update(data)
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    return jsonify(config)

@app.route('/api/projects/<project_id>/execute', methods=['POST'])
def api_execute_function(project_id):
    """执行生成功能"""
    data = request.json
    function_name = data.get('function')
    params = data.get('params', {})
    
    project_dir = PROJECTS_DIR / project_id
    config_file = project_dir / 'config.json'
    
    if not config_file.exists():
        return jsonify({'error': 'Project not found'}), 404
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # 更新参数
    config['params'].update(params)
    config['status'] = 'running'
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    # 在后台执行
    def run_generation():
        try:
            if function_name == 'generate_costume':
                run_generate_costume(project_id, config, params)
            elif function_name == 'generate_storyboard':
                run_generate_storyboard(project_id, config, params)
            elif function_name == 'generate_videos':
                run_generate_videos(project_id, config, params)
            elif function_name == 'generate_all':
                run_generate_all(project_id, config, params)
            
            config['status'] = 'completed'
        except Exception as e:
            config['status'] = 'error'
            config['error'] = str(e)
        finally:
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
    
    thread = threading.Thread(target=run_generation)
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'started', 'project_id': project_id})

def run_generate_costume(project_id, config, params):
    """执行定妆照生成 - 支持多角色"""
    description = params.get('description', config.get('description', ''))
    num_costumes = params.get('num_costumes', 3)

    # 解析描述获取所有角色
    parsed = main_pipeline.parse_description(description)
    subjects = parsed.get('subjects', ['小男孩'])

    # 创建项目目录
    project_dir = PROJECTS_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[DEBUG] description: {description}")
    print(f"[DEBUG] parsed subjects: {subjects}")

    # 为每个角色生成定妆照
    all_results = []
    for i, subject in enumerate(subjects):
        print(f"[DEBUG] Generating costume {i+1}/{len(subjects)} for: {subject}")

        try:
            results = main_pipeline.generate_costume_photos(
                subject=subject,
                description=description,
                project_dir=project_dir,
                num_variants=num_costumes,
                parsed=parsed
            )

            # 为每个结果添加角色信息
            for r in results:
                r['subject'] = subject  # 标记属于哪个角色
                # 转换为前端可访问的路径（使用 /api/output/ 路由）
                filepath = str(r['filepath'])
                # 提取文件名（现在使用简单文件名，避免子目录嵌套）
                filename = filepath.split('/')[-1]
                r['url'] = f'/api/output/{filename}'

            all_results.extend(results)
            print(f"[DEBUG] Generated {len(results)} variants for {subject}")

        except Exception as e:
            print(f"[ERROR] Failed to generate costume for {subject}: {e}")
            continue

    print(f"[DEBUG] Total costume photos: {len(all_results)}")

    config['costumes'] = all_results
    config['description'] = description
    config['subjects'] = subjects  # 保存所有角色
    config['parsed'] = parsed

    with open(PROJECTS_DIR / project_id / 'config.json', 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def run_generate_storyboard(project_id, config, params):
    """执行分镜图生成 - 支持多角色"""
    # 需要先有定妆照
    if not config.get('costumes'):
        raise Exception('需要先生成定妆照')

    # 获取所有角色的定妆照
    all_costumes = config['costumes']
    if not all_costumes:
        raise Exception('没有可用的定妆照')

    # 按角色分组选取定妆照
    costume_by_subject = {}
    for c in all_costumes:
        subject = c.get('subject', 'default')
        if subject not in costume_by_subject:
            costume_by_subject[subject] = []
        costume_by_subject[subject].append(c)

    # 使用每个角色的第一个定妆照
    selected_costumes = {}
    for subject, photos in costume_by_subject.items():
        selected_costumes[subject] = photos[0]  # 选择第一个变体

    num_shots = params.get('num_shots', 3)
    description = params.get('description', config.get('description', ''))
    # 重新解析描述，确保使用最新的
    parsed = main_pipeline.parse_description(description)
    base_seed = params.get('seed', 42) if params.get('seed', -1) > 0 else 42

    # 创建项目目录
    project_dir = PROJECTS_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    # 保存选中的定妆照路径
    config['selected_costumes'] = {
        subject: photos[0]['filepath']
        for subject, photos in costume_by_subject.items()
    }

    # 构建 costume_info 传递给分镜生成
    costume_info = {'selected': {}}
    for subject, photo_info in selected_costumes.items():
        if isinstance(photo_info, dict):
            costume_info['selected'][subject] = {
                'filepath': photo_info.get('filepath', ''),
                'prompt': photo_info.get('prompt', '')
            }
        else:
            costume_info['selected'][subject] = {'filepath': photo_info, 'prompt': ''}

    # 生成分镜
    shots = main_pipeline.generate_story_shots(description, parsed, num_shots, costume_info=costume_info)

    # 生成图片
    results = main_pipeline.generate_storyboard_images(
        project_dir=project_dir,
        shots=shots,
        base_seed=base_seed
    )

    # 为分镜图添加前端可访问的 URL
    for r in results:
        filepath = str(r['filepath'])
        filename = filepath.split('/')[-1]
        r['url'] = f'/api/output/{filename}'

    config['storyboards'] = results
    config['shots'] = shots

    with open(PROJECTS_DIR / project_id / 'config.json', 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def run_generate_videos(project_id, config, params):
    """执行视频生成"""
    if not config.get('storyboards'):
        raise Exception('需要先生成分镜图')
    
    selected_costume = config['costumes'][0] if config['costumes'] else None
    videos = []
    
    for sb in config['storyboards']:
        video_path = main_pipeline.generate_video_from_image(
            image_path=sb['filepath'],
            video_prompt=sb.get('video_prompt', ''),
            project_dir=PROJECTS_DIR / project_id,
            shot_name=f"shot_{sb['shot_num']:02d}",
            seed=params.get('seed', -1),
            reference_image=selected_costume['filepath'] if selected_costume else None
        )
        videos.append({
            'shot_num': sb['shot_num'],
            'filepath': video_path,
            'url': f'/api/output/{video_path.split("/")[-1]}' if video_path else None
        })
    
    config['videos'] = videos
    
    with open(PROJECTS_DIR / project_id / 'config.json', 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def run_generate_all(project_id, config, params):
    """执行完整流水线"""
    run_generate_costume(project_id, config, params)
    run_generate_storyboard(project_id, config, params)
    run_generate_videos(project_id, config, params)

@app.route('/api/project/<project_id>/file/<path:filename>')
def api_project_file(project_id, filename):
    """获取项目文件"""
    project_dir = PROJECTS_DIR / project_id
    return send_from_directory(str(project_dir), filename)

@app.route('/api/output/<path:filename>')
def api_output_file(filename):
    """获取输出文件"""
    return send_from_directory(str(COMFYUI_OUTPUT), filename)

@app.route('/api/input/<path:filename>')
def api_input_file(filename):
    """获取输入文件"""
    return send_from_directory(str(COMFYUI_INPUT), filename)

if __name__ == '__main__':
    print("=" * 60)
    print("故事视频生成流水线 Web UI")
    print("=" * 60)
    print(f"ComfyUI: {COMFYUI_URL}")
    print(f"项目目录: {PROJECTS_DIR}")
    print(f"访问地址: http://127.0.0.1:5001")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5001, debug=True)

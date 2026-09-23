# comfyui_workflows 项目进度记录

> 生成时间: 2026-04-19 22:50
> 端口: 5001 (原 5000 被占用)

## 一、当前项目结构

```
comfyui_workflows/
├── skills/                    # ✅ 从 huobao-drama 整合
│   ├── extractor/            # 角色/场景/道具提取规范
│   ├── grid_prompt_generator/ # 图片提示词模板（含 reference/）
│   │   └── reference/         # character/scene/shot 提示词模板
│   ├── script_rewriter/       # 小说改剧本规范
│   ├── storyboard_breaker/    # 分镜拆解规范（16字段）
│   └── voice_assigner/        # 音色分配规范
├── skills_loader.py           # ✅ 修复：真正从文件加载 skills
├── web_ui/                    # ⚠️ Flask 旧版 UI（未整合 huobao）
│   ├── app.py                 # Flask 后端 (端口5001)
│   ├── templates/index.html   # 前端页面
│   └── static/                # 静态资源
├── main_pipeline.py          # 主流水线
├── projects/                 # 项目目录（10个项目）
├── output/                   # 输出目录
│   ├── web_projects/         # Web 项目
│   ├── storyboards/          # 分镜图
│   ├── costume_photos/        # 定装照
│   └── videos/               # 生成视频
└── huobao-drama/             # ❌ 未整合（参考项目）
```

## 二、Skills 系统 ✅ 已整合

### 2.1 整合内容
| Skill | 来源 | 状态 |
|-------|------|------|
| extractor | huobao-drama | ✅ 已整合 |
| grid_prompt_generator | huobao-drama | ✅ 已整合 |
| script_rewriter | huobao-drama | ✅ 已整合 |
| storyboard_breaker | huobao-drama | ✅ 已整合 |
| voice_assigner | huobao-drama | ✅ 已整合 |

### 2.2 skills_loader.py 功能
```python
# 已实现
load_skill_md(skill_name)           # 加载 SKILL.md
load_reference_template(name)        # 加载 reference/*.md
parse_character_from_skill()         # 角色解析
parse_scene_from_text()              # 场景解析
generate_storyboard_shots()          # 分镜生成
run_script_rewriter()               # 剧本改写
run_extractor()                     # 角色+场景提取
run_storyboard_breaker()            # 分镜拆解
export_project_json()               # 项目导出
```

### 2.3 验证测试
```
✅ extractor/SKILL.md 加载: 791 字符
✅ script_rewriter/SKILL.md 加载: 834 字符
✅ storyboard_breaker/SKILL.md 加载: 1970 字符
✅ character-prompt.md 加载: 642 字符
✅ scene-prompt.md 加载: 748 字符
✅ shot-prompt.md 加载: 706 字符
✅ 完整 Pipeline 测试通过
```

## 三、Web UI ⚠️ 未整合

### 3.1 现状
| 项目 | comfyui_workflows | huobao-drama |
|------|------------------|--------------|
| 框架 | Flask + HTML | Nuxt3 (Vue3) + Hono |
| API | 内嵌 Flask | 独立 Hono (port 5679) |
| 数据库 | 无 | SQLite + Drizzle ORM |
| AI Agents | 无 | Mastra 框架 |
| 端口 | 5001 | 3013 (前端) / 5679 (后端) |

### 3.2 待整合
- [ ] huobao frontend (Nuxt3) 未复制到本项目
- [ ] huobao backend (Hono) 未复制到本项目
- [ ] 数据库 schema 未整合
- [ ] AI Agent 调用逻辑未整合

## 四、已验证功能

### 4.1 Pipeline 测试结果
```
输入: "白狐与樵夫" 故事
输出:
  - 角色: 白狐(配角), 角色(主角)
  - 场景: 神秘森林
  - 分镜: 6个镜头, 总时长60秒
  - 项目统计: 2角色/1场景/6镜头
```

### 4.2 端口配置
- Web UI: 5001 (已修改)
- ComfyUI: 127.0.0.1:8188 (不变)

## 五、下一步计划

### 5.1 短期（Web UI 整合）
- [ ] 复制 huobao frontend 到 comfyui_workflows
- [ ] 或将 skills_loader.py 暴露为 REST API
- [ ] 配置前端 API 指向本项目后端

### 5.2 中期（功能完善）
- [ ] 整合数据库 schema
- [ ] 添加 AI Agent 调用（使用 skills 规范）
- [ ] 实现 SSE 流式响应

### 5.3 长期
- [ ] 多厂商适配（MiniMax/火山引擎）
- [ ] 批量生成支持
- [ ] 项目管理界面

## 六、参考项目信息

### huobao-drama (参考，未整合)
```
位置: /home/evynlau/桌面/huobaoAIvideo/huobao-drama/
架构: Nuxt3(前端) + Hono(后端) + Mastra(AI Agents) + SQLite
端口: 3013(前端) / 5679(后端)
特点: 完整的 Agent Skill 系统
```

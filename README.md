# 自用备份，有需下载

基于 ComfyUI + Wan2.2 的短视频制作流水线：文字描述 → 定妆照 → 分镜图 → 分镜视频 → 配音 → 合成短片。

## 一键启动

双击根目录的 `总启动.bat`，GUI 会自动拉起全套环境（ComfyUI / Ollama / Fish Speech 按需）。

## 仓库结构

```
├── 总启动.bat                  # 一键启动入口
└── comfyui_workflows-main/     # 流水线项目
    ├── gui.py                  # 图形界面（环境自举）
    ├── main_pipeline.py        # 主流水线（也可命令行直接调用）
    ├── 文生图.json / shot1_i2v*.json   # ComfyUI 工作流模板
    ├── skills/                 # 剧本/分镜/提示词规范
    ├── web_ui/                 # Flask 网页界面
    ├── tools/                  # 独立小工具（查看器/监控/TTS）
    ├── docs/                   # 文档
    └── setup/                  # 模型下载与环境安装脚本
```

## 本机依赖（不在仓库内）

- `ComfyUI_windows_portable`（放在本仓库同级目录，约 60GB，含 Wan2.2 模型）
- Ollama + qwen2.5:7b（剧本生成）
- Fish Speech（openaudio-s1-mini，配音，路径 `D:\fish-speech-main`）
- ffmpeg（音视频合成，路径 `D:\ffmpeg`）

下载本仓库后需自行部署上述依赖，或参考 `setup/` 下的下载脚本。

## 命令行用法

```bash
py main_pipeline.py -d "一个小男孩在森林里遇到一只白狐" -t "配音文本"
py main_pipeline.py -d "描述" --costume-only   # 仅定妆照
```

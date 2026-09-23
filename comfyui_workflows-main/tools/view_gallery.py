#!/usr/bin/env python3
"""
图片画廊服务器 - 方便查看和放大 ComfyUI 生成的图片
"""

import http.server
import socketserver
import os
import webbrowser
from pathlib import Path

PORT = 8765
DIRECTORY = Path(__file__).parent.parent

class GalleryHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_gallery()
        else:
            super().do_GET()
    
    def send_gallery(self):
        html = self.generate_gallery_html()
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(html))
        self.end_headers()
        self.wfile.write(html.encode())
    
    def generate_gallery_html(self):
        projects_dir = DIRECTORY / 'projects'
        
        # 收集所有图片
        images = []
        for proj in sorted(projects_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if proj.is_dir():
                for subdir in ['costume_photos', 'storyboards', 'videos']:
                    subpath = proj / subdir
                    if subpath.exists():
                        for img in sorted(subpath.glob('*'), key=lambda x: x.stat().st_mtime, reverse=True):
                            if img.suffix.lower() in ['.png', '.jpg', '.jpeg', '.mp4']:
                                rel_path = img.relative_to(DIRECTORY)
                                mtime = img.stat().st_mtime
                                images.append({
                                    'path': str(rel_path).replace('\\', '/'),
                                    'name': img.name,
                                    'project': proj.name,
                                    'type': subdir,
                                    'mtime': mtime
                                })
        
        # 生成 HTML
        html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ComfyUI 图片画廊</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #1a1a2e; color: #eee; padding: 20px;
        }
        h1 { text-align: center; margin-bottom: 20px; color: #00d4ff; }
        .filters {
            text-align: center; margin-bottom: 20px;
        }
        .filters button {
            background: #16213e; color: #fff; border: 1px solid #0f3460;
            padding: 8px 16px; margin: 4px; cursor: pointer; border-radius: 4px;
        }
        .filters button:hover, .filters button.active {
            background: #0f3460; border-color: #00d4ff;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
        }
        .card {
            background: #16213e; border-radius: 8px; overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .card img {
            width: 100%; height: 200px; object-fit: cover; cursor: pointer;
            transition: transform 0.2s;
        }
        .card img:hover { transform: scale(1.02); }
        .card-info { padding: 12px; }
        .card-info .name { font-size: 14px; color: #00d4ff; word-break: break-all; }
        .card-info .meta { font-size: 12px; color: #888; margin-top: 4px; }
        .card-info .project { color: #e94560; }
        .modal {
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.9); z-index: 1000; justify-content: center;
            align-items: center; flex-direction: column;
        }
        .modal.show { display: flex; }
        .modal img { max-width: 90%; max-height: 85vh; border-radius: 4px; }
        .modal .close {
            position: absolute; top: 20px; right: 30px; font-size: 40px;
            color: #fff; cursor: pointer;
        }
        .modal .info {
            color: #888; margin-top: 10px; text-align: center;
        }
        .empty { text-align: center; color: #666; padding: 60px; }
    </style>
</head>
<body>
    <h1>🎬 ComfyUI 图片画廊</h1>
    
    <div class="filters">
        <button class="active" data-filter="all">全部</button>
        <button data-filter="costume_photos">定妆照</button>
        <button data-filter="storyboards">分镜图</button>
        <button data-filter="videos">视频</button>
    </div>
    
    <div class="grid" id="grid">
'''
        
        if not images:
            html += '<div class="empty">暂无图片<br><br>运行 main_pipeline.py 生成内容</div>'
        else:
            for img in images[:50]:  # 最多显示50张
                icon = '🎬' if img['type'] == 'videos' else '🖼️'
                if img['type'] == 'videos':
                    media_tag = f'<video src="{img["path"]}" muted loop></video>'
                else:
                    media_tag = f'<img src="{img["path"]}" alt="{img["name"]}" onclick="showModal(this)">'
                html += f'''
        <div class="card" data-type="{img['type']}">
            {media_tag}
            <div class="card-info">
                <div class="name">{icon} {img['name']}</div>
                <div class="meta">
                    <span class="project">{img['project']}</span> · {img['type']}
                </div>
            </div>
        </div>
'''
        
        html += '''
    </div>
    
    <div class="modal" id="modal">
        <span class="close" onclick="closeModal()">&times;</span>
        <img id="modalImg" src="">
        <div class="info" id="modalInfo"></div>
    </div>
    
    <script>
        // Filter buttons
        document.querySelectorAll('.filters button').forEach(btn => {
            btn.onclick = () => {
                document.querySelectorAll('.filters button').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const filter = btn.dataset.filter;
                document.querySelectorAll('.card').forEach(card => {
                    card.style.display = (!filter || filter === 'all' || card.dataset.type === filter) ? 'block' : 'none';
                });
            };
        });
        
        function showModal(img) {
            document.getElementById('modalImg').src = img.src;
            document.getElementById('modalInfo').textContent = img.alt;
            document.getElementById('modal').classList.add('show');
        }
        
        function closeModal() {
            document.getElementById('modal').classList.remove('show');
        }
        
        document.getElementById('modal').onclick = (e) => {
            if (e.target.id === 'modal') closeModal();
        };
        
        document.onkeydown = (e) => {
            if (e.key === 'Escape') closeModal();
        };
    </script>
</body>
</html>'''
        return html

if __name__ == '__main__':
    os.chdir(DIRECTORY)
    with socketserver.TCPServer(("", PORT), GalleryHandler) as httpd:
        url = f"http://localhost:{PORT}"
        print(f"\n🖼️ 图片画廊已启动: {url}")
        print(f"   打开浏览器访问查看图片")
        print(f"   按 Ctrl+C 停止服务器\n")
        webbrowser.open(url)
        httpd.serve_forever()

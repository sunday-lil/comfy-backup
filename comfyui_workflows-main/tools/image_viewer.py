#!/usr/bin/env python3
"""
图片查看器 - 支持双击放大查看
"""

import os
import http.server
import socketserver
from pathlib import Path
import webbrowser

PORT = 8899
WORKFLOW_DIR = Path(__file__).parent.parent
OUTPUT_DIR = WORKFLOW_DIR / "output"

HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>📷 图片查看器</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #1a1a2e; 
            color: #eee;
            min-height: 100vh;
        }
        .header {
            background: #16213e;
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #0f3460;
        }
        .header h1 { font-size: 1.2rem; color: #e94560; }
        .header a { color: #4ecca3; text-decoration: none; }
        .header a:hover { text-decoration: underline; }
        
        .tabs {
            display: flex;
            gap: 5px;
            padding: 15px 20px;
            background: #16213e;
            overflow-x: auto;
        }
        .tab {
            padding: 8px 16px;
            background: #0f3460;
            border: none;
            border-radius: 20px;
            color: #aaa;
            cursor: pointer;
            white-space: nowrap;
            font-size: 0.9rem;
        }
        .tab:hover { background: #1a4a7a; color: #fff; }
        .tab.active { background: #e94560; color: #fff; }
        
        .gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
            padding: 20px;
        }
        .card {
            background: #16213e;
            border-radius: 12px;
            overflow: hidden;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(233, 69, 96, 0.3);
        }
        .card img {
            width: 100%;
            aspect-ratio: 1;
            object-fit: cover;
            display: block;
        }
        .card-info {
            padding: 12px;
        }
        .card-title {
            font-size: 0.85rem;
            color: #4ecca3;
            margin-bottom: 5px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .card-meta {
            font-size: 0.75rem;
            color: #888;
        }
        
        /* 放大查看模态框 */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.95);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            flex-direction: column;
        }
        .modal.active { display: flex; }
        .modal img {
            max-width: 95vw;
            max-height: 85vh;
            object-fit: contain;
            border-radius: 8px;
            box-shadow: 0 0 50px rgba(233, 69, 96, 0.5);
        }
        .modal-info {
            margin-top: 20px;
            text-align: center;
            color: #888;
        }
        .modal-info .filename { color: #4ecca3; font-size: 1.1rem; }
        .modal-info .path { font-size: 0.85rem; margin-top: 5px; }
        .modal-close {
            position: absolute;
            top: 20px;
            right: 30px;
            font-size: 2rem;
            color: #888;
            cursor: pointer;
            transition: color 0.2s;
        }
        .modal-close:hover { color: #e94560; }
        .modal-nav {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            font-size: 3rem;
            color: #888;
            cursor: pointer;
            padding: 20px;
            transition: color 0.2s;
        }
        .modal-nav:hover { color: #e94560; }
        .modal-prev { left: 20px; }
        .modal-next { right: 20px; }
        
        .empty {
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }
        .empty-icon { font-size: 4rem; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📷 ComfyUI 图片查看器</h1>
        <a href="http://127.0.0.1:8188" target="_blank">→ ComfyUI</a>
    </div>
    
    <div class="tabs" id="tabs"></div>
    
    <div class="gallery" id="gallery">
        <div class="empty">
            <div class="empty-icon">📂</div>
            <div>暂无图片</div>
        </div>
    </div>
    
    <!-- 放大查看模态框 -->
    <div class="modal" id="modal">
        <span class="modal-close" onclick="closeModal()">×</span>
        <span class="modal-nav modal-prev" onclick="prevImage()">‹</span>
        <span class="modal-nav modal-next" onclick="nextImage()">›</span>
        <img id="modal-img" src="" alt="">
        <div class="modal-info">
            <div class="filename" id="modal-filename"></div>
            <div class="path" id="modal-path"></div>
        </div>
    </div>
    
    <script>
        let currentImages = [];
        let currentIndex = 0;
        
        const categories = [
            { id: 'all', name: '全部' },
            { id: 'costume_photos', name: '🎭 定妆照' },
            { id: 'storyboards', name: '🖼️ 分镜图' },
            { id: 'videos', name: '🎬 视频' },
            { id: 'test', name: '🧪 测试' },
        ];
        
        async function scanFolder(dir, subfolder) {
            try {
                const resp = await fetch(`/_scan?dir=${encodeURIComponent(dir)}`);
                const files = await resp.json();
                return files.map(f => ({
                    dir: dir,
                    subfolder: subfolder,
                    name: f.name,
                    path: f.path,
                    type: f.type
                }));
            } catch {
                return [];
            }
        }
        
        async function init() {
            // 渲染标签页
            const tabsEl = document.getElementById('tabs');
            categories.forEach(cat => {
                const btn = document.createElement('button');
                btn.className = 'tab' + (cat.id === 'all' ? ' active' : '');
                btn.textContent = cat.name;
                btn.onclick = () => switchTab(cat.id);
                tabsEl.appendChild(btn);
            });
            
            // 扫描图片
            currentImages = [];
            for (const cat of categories.slice(1)) {
                const files = await scanFolder(cat.id, cat.id);
                currentImages.push(...files);
            }
            
            renderGallery('all');
        }
        
        function switchTab(id) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            renderGallery(id);
        }
        
        function renderGallery(filter) {
            const gallery = document.getElementById('gallery');
            const images = filter === 'all' 
                ? currentImages 
                : currentImages.filter(img => img.subfolder === filter);
            
            if (images.length === 0) {
                gallery.innerHTML = `
                    <div class="empty">
                        <div class="empty-icon">📭</div>
                        <div>该目录下暂无图片</div>
                    </div>`;
                return;
            }
            
            gallery.innerHTML = images.map((img, i) => `
                <div class="card" onclick="openModal(${i})">
                    <img src="/view?path=${encodeURIComponent(img.path)}" alt="${img.name}">
                    <div class="card-info">
                        <div class="card-title">${img.name}</div>
                        <div class="card-meta">${img.subfolder}</div>
                    </div>
                </div>
            `).join('');
        }
        
        function openModal(index) {
            currentIndex = index;
            const img = currentImages[index];
            document.getElementById('modal-img').src = `/view?path=${encodeURIComponent(img.path)}`;
            document.getElementById('modal-filename').textContent = img.name;
            document.getElementById('modal-path').textContent = img.path;
            document.getElementById('modal').classList.add('active');
        }
        
        function closeModal() {
            document.getElementById('modal').classList.remove('active');
        }
        
        function prevImage() {
            currentIndex = (currentIndex - 1 + currentImages.length) % currentImages.length;
            openModal(currentIndex);
        }
        
        function nextImage() {
            currentIndex = (currentIndex + 1) % currentImages.length;
            openModal(currentIndex);
        }
        
        // 键盘控制
        document.addEventListener('keydown', e => {
            if (!document.getElementById('modal').classList.contains('active')) return;
            if (e.key === 'Escape') closeModal();
            if (e.key === 'ArrowLeft') prevImage();
            if (e.key === 'ArrowRight') nextImage();
        });
        
        init();
    </script>
</body>
</html>
"""

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WORKFLOW_DIR), **kwargs)
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_content(HTML.encode(), content_type='text/html')
        elif self.path.startswith('/view'):
            # 解析 path 参数
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            if 'path' in params:
                file_path = params['path'][0]
                return super().do_GET()
            # 或者解析 filename 和 subfolder
            if 'filename' in params:
                filename = params['filename'][0]
                subfolder = params.get('subfolder', [''])[0]
                self.path = f'/output/{subfolder}/{filename}' if subfolder else f'/output/{filename}'
                return super().do_GET()
        elif self.path.startswith('/_scan'):
            from urllib.parse import urlparse, parse_qs
            import json
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            dir_path = params.get('dir', [''])[0]
            # 相对路径则基于 output 目录解析
            if dir_path and not os.path.isabs(dir_path):
                dir_path = os.path.join(str(OUTPUT_DIR), dir_path)
            
            files = []
            if os.path.isdir(dir_path):
                for f in sorted(os.listdir(dir_path)):
                    fp = os.path.join(dir_path, f)
                    if os.path.isfile(fp):
                        ext = os.path.splitext(f)[1].lower()
                        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.mp4', '.webp']:
                            files.append({
                                'name': f,
                                'path': fp,
                                'type': 'video' if ext in ['.mp4'] else 'image'
                            })
            
            self.send_content(json.dumps(files).encode(), content_type='application/json')
        else:
            super().do_GET()
    
    def send_content(self, content, content_type='text/html'):
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', len(content))
        self.end_headers()
        self.wfile.write(content)

if __name__ == '__main__':
    os.chdir(WORKFLOW_DIR)
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}"
        print(f"\n🖼️ 图片查看器已启动: {url}\n")
        webbrowser.open(url)
        httpd.serve_forever()

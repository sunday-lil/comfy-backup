# -*- coding: utf-8 -*-
"""
短视频制作器 GUI
打开时自动启动环境（ComfyUI / Ollama），输入文本 → 一键调用生成脚本。
用法: py gui.py
"""
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from urllib.request import urlopen

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COMFYUI_PY = r"D:\comfy\ComfyUI_windows_portable\python_embeded\python.exe"
COMFYUI_MAIN = r"D:\comfy\ComfyUI_windows_portable\ComfyUI\main.py"
OLLAMA_EXE = shutil.which("ollama") or r"D:\OLLAMA\ollama.exe"
LOG_DIR = os.path.join(BASE_DIR, "setup", "logs")

COMFYUI_URL = "http://127.0.0.1:8188/system_stats"
OLLAMA_URL = "http://localhost:11434/api/tags"

# TTS(Fish Speech) 由 main_pipeline 在配音阶段按需启动/停止，无需预启动（节省显存）


def http_ok(url: str, timeout: int = 3) -> bool:
    try:
        with urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("短视频制作器")
        self.geometry("780x720")
        self.minsize(680, 600)

        self.proc = None
        self.log_queue = queue.Queue()
        self.final_path = None
        self.status_labels = {}

        self._build_ui()
        # 打开时自动启动所有环境
        self.after(100, self._bootstrap_env)

    # ============ 界面 ============
    def _build_ui(self):
        pad = {"padx": 10, "pady": 4}

        title = ttk.Label(self, text="短视频制作器", font=("Microsoft YaHei UI", 16, "bold"))
        title.pack(pady=(10, 2))

        # ---- 环境状态 ----
        env_frame = ttk.LabelFrame(self, text="环境状态（自动启动）")
        env_frame.pack(fill="x", **pad)

        self.status_labels["comfyui"] = self._status_chip(env_frame, "ComfyUI (生图/生视频)", "检测中…")
        self.status_labels["ollama"] = self._status_chip(env_frame, "Ollama (剧本)", "检测中…")
        self.status_labels["ffmpeg"] = self._status_chip(env_frame, "ffmpeg (合成)", "检测中…")
        self.status_labels["fish"] = self._status_chip(env_frame, "Fish Speech (配音)", "按需自动")

        # ---- 输入 ----
        in_frame = ttk.Frame(self)
        in_frame.pack(fill="both", expand=False, **pad)

        ttk.Label(in_frame, text="场景描述（必填）：").grid(row=0, column=0, sticky="nw", pady=(6, 0))
        self.desc_text = tk.Text(in_frame, height=3, wrap="word", font=("Microsoft YaHei UI", 10))
        self.desc_text.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        ttk.Label(in_frame, text="配音文本（可选，留空则无声）：").grid(row=2, column=0, sticky="nw")
        self.tts_text = tk.Text(in_frame, height=2, wrap="word", font=("Microsoft YaHei UI", 10))
        self.tts_text.grid(row=3, column=0, sticky="ew", pady=(0, 6))

        opt_row = ttk.Frame(in_frame)
        opt_row.grid(row=4, column=0, sticky="ew")
        ttk.Label(opt_row, text="分镜数量：").pack(side="left")
        self.shots = ttk.Spinbox(opt_row, from_=1, to=6, width=4, value=3)
        self.shots.pack(side="left", padx=(0, 16))

        self.make_btn = ttk.Button(opt_row, text="🎬 开始制作", command=self.on_make)
        self.make_btn.pack(side="right")

        in_frame.columnconfigure(0, weight=1)

        # ---- 日志 ----
        log_frame = ttk.LabelFrame(self, text="制作日志")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log_box = scrolledtext.ScrolledText(log_frame, height=14, state="disabled",
                                                 font=("Consolas", 9))
        self.log_box.pack(fill="both", expand=True, padx=6, pady=6)

        # ---- 状态栏 ----
        self.bar = ttk.Label(self, text="就绪", anchor="w", relief="sunken", padding=(6, 2))
        self.bar.pack(fill="x", side="bottom")

    def _status_chip(self, parent, name: str, initial: str) -> ttk.Label:
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=8, pady=2)
        ttk.Label(row, text=name, width=26, anchor="w").pack(side="left")
        chip = ttk.Label(row, text=initial, anchor="w")
        chip.pack(side="left")
        return chip

    def set_status(self, key: str, text: str, ok: bool | None = None):
        color = {"good": "#107c10", "bad": "#c42b1c", "wait": "#b18b00"}.get(
            {True: "good", False: "bad", None: "wait"}[ok], "gray"
        )
        def upd():
            self.status_labels[key].config(text=text, foreground=color)
        self.after(0, upd)

    def log(self, line: str):
        def upd():
            self.log_box.config(state="normal")
            self.log_box.insert("end", line + "\n")
            self.log_box.see("end")
            self.log_box.config(state="disabled")
        self.after(0, upd)

    def set_bar(self, text: str):
        self.after(0, lambda: self.bar.config(text=text))

    # ============ 环境自启动 ============
    def _bootstrap_env(self):
        threading.Thread(target=self._env_thread, daemon=True).start()

    def _env_thread(self):
        os.makedirs(LOG_DIR, exist_ok=True)

        # ffmpeg（无需启动，只检查）
        if shutil.which("ffmpeg"):
            self.set_status("ffmpeg", "可用", True)
        else:
            self.set_status("ffmpeg", "未找到（检查 PATH）", False)

        # ComfyUI
        self.set_status("comfyui", "检测中…", None)
        if http_ok(COMFYUI_URL):
            self.set_status("comfyui", "运行中", True)
        elif not os.path.exists(COMFYUI_PY):
            self.set_status("comfyui", f"未找到: {COMFYUI_PY}", False)
        else:
            self.set_status("comfyui", "启动中（加载约 1 分钟）…", None)
            self.log("[环境] 启动 ComfyUI…")
            with open(os.path.join(LOG_DIR, "comfyui_run.log"), "a", encoding="utf-8") as lf:
                subprocess.Popen(
                    [COMFYUI_PY, "-s", COMFYUI_MAIN, "--port", "8188"],
                    stdout=lf, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            if self._wait_service("comfyui", COMFYUI_URL, 120):
                self.set_status("comfyui", "运行中", True)
            else:
                self.set_status("comfyui", "启动失败（见 setup/logs/comfyui_run.log）", False)

        # Ollama
        self.set_status("ollama", "检测中…", None)
        if http_ok(OLLAMA_URL):
            self.set_status("ollama", "运行中", True)
        elif not os.path.exists(OLLAMA_EXE):
            self.set_status("ollama", "未找到 ollama", False)
        else:
            self.set_status("ollama", "启动中…", None)
            self.log("[环境] 启动 Ollama…")
            subprocess.Popen(
                [OLLAMA_EXE, "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if self._wait_service("ollama", OLLAMA_URL, 30):
                self.set_status("ollama", "运行中", True)
            else:
                self.set_status("ollama", "启动失败（请手动运行 ollama serve）", False)

        self.set_bar("环境就绪，输入描述后点击「开始制作」")

    def _wait_service(self, key: str, url: str, seconds: int) -> bool:
        for _ in range(seconds // 3):
            time.sleep(3)
            if http_ok(url):
                return True
        return http_ok(url)

    # ============ 制作 ============
    def on_make(self):
        if self.proc and self.proc.poll() is None:
            messagebox.showwarning("进行中", "已有任务在制作中，请等待完成")
            return

        desc = self.desc_text.get("1.0", "end").strip()
        if not desc:
            messagebox.showwarning("缺少输入", "请先填写场景描述")
            self.desc_text.focus_set()
            return
        tts = self.tts_text.get("1.0", "end").strip()
        shots = str(int(self.shots.get()))

        # 把用户输入拼成命令调用生成脚本
        cmd = ["py", "main_pipeline.py", "-d", desc, "-s", shots]
        if tts:
            cmd += ["-t", tts]

        self.log("=" * 60)
        self.log(f"[命令] {' '.join(cmd[:2])} -d <描述{len(desc)}字> -s {shots}"
                 + (f" -t <配音{len(tts)}字>" if tts else ""))
        self.set_bar("制作中…（视频约 3.5 分钟/段，请耐心等待）")
        self.make_btn.config(state="disabled")
        self.final_path = None

        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        self.proc = subprocess.Popen(
            cmd, cwd=BASE_DIR, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        threading.Thread(target=self._read_output, daemon=True).start()
        self.after(150, self._poll_output)

    def _read_output(self):
        for line in self.proc.stdout:
            self.log_queue.put(line.rstrip("\n"))
        self.log_queue.put(None)  # EOF

    def _poll_output(self):
        finished = False
        try:
            while True:
                item = self.log_queue.get_nowait()
                if item is None:
                    finished = True
                    break
                self.log(item)
                m = re.search(r"最终成品:\s*(.+\.mp4)", item)
                if m:
                    self.final_path = m.group(1).strip()
        except queue.Empty:
            pass

        if not finished:
            self.after(150, self._poll_output)
            return

        # 进程结束
        self.make_btn.config(state="normal")
        code = self.proc.returncode
        if code == 0 and self.final_path:
            self.set_bar(f"完成: {self.final_path}")
            self.log(f"[完成] {self.final_path}")
            if messagebox.askyesno("制作完成", f"短视频已生成:\n{self.final_path}\n\n是否打开所在文件夹？"):
                os.startfile(os.path.dirname(self.final_path))
        elif code == 0:
            self.set_bar("完成（未检测到成品路径，请查看日志）")
            messagebox.showinfo("完成", "流水线已结束，详情见日志")
        else:
            self.set_bar(f"失败（退出码 {code}），请查看日志")
            messagebox.showerror("失败", f"流水线异常退出（代码 {code}），请查看日志排查")


if __name__ == "__main__":
    app = App()
    app.mainloop()

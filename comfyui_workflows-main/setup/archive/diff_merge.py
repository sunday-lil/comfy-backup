# -*- coding: utf-8 -*-
"""诊断: 对比合并文件与原始分片中同一张量的字节是否一致"""
import sys
sys.path.insert(0, r"D:\comfyui_workflows-main\setup")
from merge_gguf import parse_header, tensor_bytes

MERGED = r"D:\ollama_models\qwen2.5-7b-instruct-q4_k_m.gguf"
S1 = r"D:\ollama_models\qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf"
S2 = r"D:\ollama_models\qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf"

def get(path, tname, nbytes=64):
    kv, tensors, he = parse_header(path)
    data_start = (he + 31) // 32 * 32
    for name, dims, gtype, offset in tensors:
        if name == tname:
            size = min(tensor_bytes(gtype, dims), nbytes)
            with open(path, "rb") as f:
                f.seek(data_start + offset)
                return f.read(size), gtype
    return None, None

for tn in [b"blk.24.attn_norm.weight", b"blk.0.attn_norm.weight", b"output.weight", b"blk.23.ffn_gate.weight", b"token_embd.weight"]:
    m, gm = get(MERGED, tn)
    s1, g1 = get(S1, tn)
    s2, g2 = get(S2, tn)
    src = s1 if s1 else s2
    which = "分片1" if s1 else "分片2"
    if m and src:
        same = m == src[:len(m)]
        print(f"{tn.decode():32s} 类型={gm} 来源={which} 一致={same}")
        if not same:
            print(f"  合并: {m[:24].hex()}")
            print(f"  原始: {src[:24].hex()}")
            # 检查是否是移位
            for shift in range(-4, 5):
                if shift == 0:
                    continue
                # 在合并文件中找原始字节
                pass

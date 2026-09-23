# -*- coding: utf-8 -*-
"""检查原始分片中张量数据的字节序"""
import sys, struct
sys.path.insert(0, r"D:\comfyui_workflows-main\setup")
from merge_gguf import parse_header, tensor_bytes

def h16(b, big):
    return struct.unpack('>e' if big else '<e', b)[0]

for p, tn in [
    (r"D:\ollama_models\qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf", b"blk.0.attn_norm.weight"),
    (r"D:\ollama_models\qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf", b"token_embd.weight"),
    (r"D:\ollama_models\qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf", b"blk.22.attn_norm.weight"),
    (r"D:\ollama_models\qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf", b"blk.24.attn_norm.weight"),
    (r"D:\ollama_models\qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf", b"output_norm.weight"),
]:
    kv, tensors, he = parse_header(p)
    data_start = (he + 31) // 32 * 32
    for name, dims, gtype, offset in tensors:
        if name == tn:
            size = tensor_bytes(gtype, dims)
            with open(p, "rb") as f:
                f.seek(data_start + offset)
                data = f.read(min(size, 1024))
            print(f"{tn.decode()} 类型={gtype} 分片={'1' if '00001' in p else '2'}")
            if gtype == 0:
                le = [round(struct.unpack('<f', data[i*4:(i+1)*4])[0], 5) for i in range(6)]
                be = [round(struct.unpack('>f', data[i*4:(i+1)*4])[0], 5) for i in range(6)]
                print(f"  LE前6值: {le}")
                print(f"  BE前6值: {be}")
            elif gtype == 14:
                for blk in range(3):
                    b = data[blk*210+208:blk*210+210]
                    print(f"  块{blk} d字节={b.hex()} LE={h16(b, False):.6g} BE={h16(b, True):.6g}")
            elif gtype == 12:
                for blk in range(3):
                    d = data[blk*144:blk*144+2]
                    dm = data[blk*144+2:blk*144+4]
                    print(f"  块{blk} d={d.hex()} LE={h16(d, False):.6g} BE={h16(d, True):.6g} | dmin={dm.hex()} LE={h16(dm, False):.6g} BE={h16(dm, True):.6g}")

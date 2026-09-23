# -*- coding: utf-8 -*-
"""全量校验合并 GGUF: 逐张量比对合并文件 vs 原始分片（按各自 general.alignment 对齐 data_start）"""
import sys, struct, hashlib
sys.path.insert(0, r"D:\comfyui_workflows-main\setup")
from merge_gguf import parse_header, tensor_bytes

MERGED = r"D:\ollama_models\qwen2.5-7b-instruct-q4_k_m.gguf"
SHARDS = [
    r"D:\ollama_models\qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf",
    r"D:\ollama_models\qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf",
]

def load_info(path):
    kv, tensors, he = parse_header(path)
    align = 32
    for key, vtype, raw in kv:
        if key == b"general.alignment":
            align = struct.unpack("<I", raw)[0]
    data_start = (he + align - 1) // align * align
    print(f"{path.split(chr(92))[-1]}: header_end={he} align={align} data_start={data_start} "
          f"(pad={data_start-he}) tensors={len(tensors)}")
    return tensors, data_start

def main():
    mt, mds = load_info(MERGED)
    shard_info = [load_info(p) for p in SHARDS]

    # 建立分片张量索引
    index = {}
    for si, (tensors, ds) in enumerate(shard_info):
        for name, dims, gtype, offset in tensors:
            index[name] = (si, offset, tensor_bytes(gtype, dims))

    # 校验1: 合并文件张量数一致
    assert len(mt) == len(index), f"张量数不符: {len(mt)} vs {len(index)}"

    # 校验2: 合并文件内部布局连续且对齐
    kv_m, _, he_m = parse_header(MERGED)
    align_m = 32
    for key, vtype, raw in kv_m:
        if key == b"general.alignment":
            align_m = struct.unpack("<I", raw)[0]
    pos = 0
    for name, dims, gtype, offset in mt:
        if offset != pos:
            print(f"[FAIL] 合并文件布局不连续: {name.decode()} offset={offset} 预期={pos}")
            return 1
        pos = (offset + tensor_bytes(gtype, dims) + align_m - 1) // align_m * align_m
    print(f"[OK] 合并文件内部布局连续, 数据区末尾={pos}")

    # 校验3: 逐张量全量字节比对
    files = [open(MERGED, "rb")] + [open(p, "rb") for p in SHARDS]
    bad = 0
    total_bytes = 0
    for name, dims, gtype, offset in mt:
        si, s_off, size = index[name]
        files[0].seek(mds + offset)
        files[si + 1].seek(shard_info[si][1] + s_off)
        remaining = size
        while remaining:
            chunk = min(8 * 1024 * 1024, remaining)
            a = files[0].read(chunk)
            b = files[si + 1].read(chunk)
            if a != b:
                print(f"[FAIL] {name.decode()}: 字节不一致 (块起始 {mds+offset})")
                bad += 1
                break
            remaining -= len(a)
        total_bytes += size
        if bad >= 5:
            break
    for f in files:
        f.close()
    if bad:
        print(f"[FAIL] 共 {bad} 个张量不一致")
        return 1
    print(f"[OK] 全部 {len(mt)} 个张量字节一致, 总计 {total_bytes/1073741824:.2f}GB")
    return 0

if __name__ == "__main__":
    sys.exit(main())

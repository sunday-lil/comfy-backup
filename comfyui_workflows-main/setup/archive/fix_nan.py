# -*- coding: utf-8 -*-
"""扫描并修复 GGUF 中 fp16 scale 字段的 NaN/Inf（官方 Qwen2.5-7B q4_k_m 导出缺陷）
q4_K 块144字节: d@+0, dmin@+2 | q6_K 块210字节: d@+208 | f32: 直接扫
NaN/Inf 判定: (u16 & 0x7C00) == 0x7C00
修复: 写 0x0000 (fp16 0.0)
用法: py fix_nan.py file.gguf [--dry-run]
"""
import sys, struct
import numpy as np
sys.path.insert(0, r"D:\comfyui_workflows-main\setup")
from merge_gguf import parse_header, tensor_bytes

def patch_tensor(f, abs_off, gtype, size, dry):
    """返回 (坏scale数, 修复数)"""
    f.seek(abs_off)
    data = f.read(size)
    if gtype == 0:  # f32
        arr = np.frombuffer(data, dtype=np.float32)
        bad_mask = np.isnan(arr) | np.isinf(arr)
        n = int(bad_mask.sum())
        if n and not dry:
            idx = np.nonzero(bad_mask)[0]
            zeros = np.zeros(n, dtype=np.float32)
            # 就地覆盖对应位置
            new = arr.copy()
            new[idx] = zeros
            f.seek(abs_off)
            f.write(new.tobytes())
        return n, n
    if gtype == 12:  # q4_K: 每块144字节, d@u16[0], dmin@u16[1]
        u16 = np.frombuffer(data, dtype=np.uint16).reshape(-1, 72)[:, :2]
        bad = (u16 & np.uint16(0x7C00)) == np.uint16(0x7C00)
        n = int(bad.sum())
        if n and not dry:
            rows, cols = np.nonzero(bad)
            for r, c in zip(rows, cols):
                pos = abs_off + (int(r) * 144) + (int(c) * 2)
                f.seek(pos)
                f.write(b"\x00\x00")
        return n, n
    if gtype == 14:  # q6_K: 每块210字节, d@字节208 = u16索引104
        u16 = np.frombuffer(data, dtype=np.uint16).reshape(-1, 105)[:, 104]
        bad = (u16 & np.uint16(0x7C00)) == np.uint16(0x7C00)
        n = int(bad.sum())
        if n and not dry:
            rows = np.nonzero(bad)[0]
            for r in rows:
                pos = abs_off + (int(r) * 210) + 208
                f.seek(pos)
                f.write(b"\x00\x00")
        return n, n
    return 0, 0  # 其他类型不检查

def main(path, dry):
    kv, tensors, header_end = parse_header(path)
    # 数据区起点 = header_end 对齐到32
    align = 32
    for key, vtype, raw in kv:
        if key == b"general.alignment":
            align = struct.unpack("<I", raw)[0]
    data_start = (header_end + align - 1) // align * align
    # 需要重新计算每个张量的数据起点: 布局是紧密排列的
    pos = 0
    total_bad = 0
    mode = "r+b" if not dry else "rb"
    with open(path, mode) as f:
        for name, dims, gtype, offset in tensors:
            size = tensor_bytes(gtype, dims)
            n, _ = patch_tensor(f, data_start + offset, gtype, size, dry)
            if n:
                print(f"  {name.decode()}: {n} 个坏scale ({'已修复' if not dry else '未修复(试运行)'})")
                total_bad += n
    print(f"总计: {total_bad} 个坏scale {'(试运行,未写入)' if dry else '已全部修复为0.0'}")

if __name__ == "__main__":
    main(sys.argv[1], "--dry-run" in sys.argv)

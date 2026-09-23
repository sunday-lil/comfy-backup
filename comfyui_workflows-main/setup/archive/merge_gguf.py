# -*- coding: utf-8 -*-
"""合并 GGUF 分片为单文件（复刻 llama.cpp gguf-split --merge 逻辑）
关键: llama.cpp 加载器要求张量数据按头部列出顺序紧密排列(对齐到 general.alignment)，
因此必须按张量实际大小重新计算偏移，而不是简单拼接数据区。
用法: py merge_gguf.py shard1.gguf shard2.gguf output.gguf
"""
import struct, sys, os

MAGIC = 0x46554747  # "GGUF"
FIXED_SIZE = {0:1, 1:1, 2:2, 3:2, 4:4, 5:4, 6:4, 7:1, 10:8, 11:8, 12:8}
# GGML 类型: {type: (每块字节数, 每块元素数)}
GGML_TYPES = {
    0: (4, 1),      # F32
    1: (2, 1),      # F16
    2: (18, 32),    # Q4_0
    3: (20, 32),    # Q4_1
    6: (22, 32),    # Q5_0
    7: (24, 32),    # Q5_1
    8: (34, 32),    # Q8_0
    10: (84, 256),  # Q2_K
    11: (110, 256), # Q3_K
    12: (144, 256), # Q4_K
    13: (176, 256), # Q5_K
    14: (210, 256), # Q6_K
    25: (2, 1),     # BF16
}

class Reader:
    def __init__(self, f):
        self.f = f
    def read(self, n):
        b = self.f.read(n)
        if len(b) != n:
            raise EOFError(f"需要{n}字节,只读到{len(b)}")
        return b
    def u32(self): return struct.unpack("<I", self.read(4))[0]
    def u64(self): return struct.unpack("<Q", self.read(8))[0]
    def string(self):
        n = self.u64()
        return self.read(n)
    def value_raw(self, vtype):
        if vtype in FIXED_SIZE:
            return self.read(FIXED_SIZE[vtype])
        if vtype == 8:
            n = self.u64()
            return struct.pack("<Q", n) + self.read(n)
        if vtype == 9:  # array
            etype = self.u32()
            count = self.u64()
            raw = [struct.pack("<IQ", etype, count)]
            for _ in range(count):
                raw.append(self.value_raw(etype))
            return b"".join(raw)
        raise ValueError(f"未知值类型 {vtype}")

def tensor_bytes(gtype, dims):
    if gtype not in GGML_TYPES:
        raise ValueError(f"未实现的GGML类型 {gtype}, 请补充 GGML_TYPES 表")
    bpb, epb = GGML_TYPES[gtype]
    n = 1
    for d in dims:
        n *= d
    blocks = (n + epb - 1) // epb
    return blocks * bpb

def parse_header(path):
    kv, tensors = [], []
    with open(path, "rb") as f:
        r = Reader(f)
        if r.u32() != MAGIC:
            raise ValueError(f"{path}: 非GGUF文件")
        version = r.u32()
        if version != 3:
            raise ValueError(f"{path}: 不支持的GGUF版本 {version}")
        tensor_count, kv_count = r.u64(), r.u64()
        for _ in range(kv_count):
            key = r.string()
            vtype = r.u32()
            kv.append((key, vtype, r.value_raw(vtype)))
        for _ in range(tensor_count):
            name = r.string()
            n_dims = r.u32()
            dims = [struct.unpack("<q", r.read(8))[0] for _ in range(n_dims)]
            gtype = r.u32()
            offset = r.u64()
            tensors.append((name, dims, gtype, offset))
        header_end = f.tell()
    return kv, tensors, header_end

def w_string(f, b):
    f.write(struct.pack("<Q", len(b)))
    f.write(b)

def main(s1, s2, out):
    print(f"解析分片1: {s1}")
    kv1, t1, he1 = parse_header(s1)
    print(f"  KV={len(kv1)} 张量={len(t1)}")
    print(f"解析分片2: {s2}")
    kv2, t2, he2 = parse_header(s2)
    print(f"  KV={len(kv2)} 张量={len(t2)}")
    if len(t1) + len(t2) != 339:
        print(f"警告: 张量总数 {len(t1)+len(t2)} != 预期 339")

    align = 32
    for key, vtype, raw in kv1:
        if key == b"general.alignment":
            align = struct.unpack("<I", raw)[0]
    print(f"对齐={align}")

    # 校验: 分片内部张量应为紧密排列,验证大小计算正确
    for label, tensors, he, path in [("分片1", t1, he1, s1), ("分片2", t2, he2, s2)]:
        pos = 0
        for name, dims, gtype, offset in tensors:
            if offset != pos:
                raise SystemExit(f"{label} 内部布局不连续: {name.decode()} offset={offset} 预期={pos}, 大小表有误")
            pos = (offset + tensor_bytes(gtype, dims) + align - 1) // align * align
        print(f"{label} 大小校验通过, 数据区末尾={pos}")

    # 合并: 分片1的KV(去掉split.*) + 张量重排偏移
    merged_kv = [(k, t, r) for k, t, r in kv1 if not k.startswith(b"split.")]
    merged = [(n, d, g, o, 1) for n, d, g, o in t1] + [(n, d, g, o, 2) for n, d, g, o in t2]

    # 重新分配偏移: 紧密排列
    pos, layout = 0, []
    for name, dims, gtype, old_off, src in merged:
        new_off = (pos + align - 1) // align * align
        layout.append((name, dims, gtype, old_off, new_off, src))
        pos = new_off + tensor_bytes(gtype, dims)
    print(f"合并后: KV={len(merged_kv)} 张量={len(layout)} 数据区={pos/1073741824:.2f}GB")

    src_files = {1: open(s1, "rb"), 2: open(s2, "rb")}
    # 关键修复: 张量 offset 相对于"对齐后的数据区起点"，不是 header_end
    src_header = {1: (he1 + align - 1) // align * align, 2: (he2 + align - 1) // align * align}
    with open(out, "wb") as f:
        f.write(struct.pack("<II", MAGIC, 3))
        f.write(struct.pack("<Q", len(layout)))
        f.write(struct.pack("<Q", len(merged_kv)))
        for key, vtype, raw in merged_kv:
            w_string(f, key)
            f.write(struct.pack("<I", vtype))
            f.write(raw)
        for name, dims, gtype, _, new_off, _ in layout:
            w_string(f, name)
            f.write(struct.pack("<I", len(dims)))
            for d in dims:
                f.write(struct.pack("<q", d))
            f.write(struct.pack("<I", gtype))
            f.write(struct.pack("<Q", new_off))
        # 头结束位置对齐
        pos = f.tell()
        f.write(b"\x00" * ((pos + align - 1) // align * align - pos))
        # 按新布局逐张量拷贝数据
        written = 0
        cur = f.tell()
        for name, dims, gtype, old_off, new_off, src in layout:
            size = tensor_bytes(gtype, dims)
            if new_off + size < cur:
                raise SystemExit(f"布局冲突: {name.decode()}")
            f.write(b"\x00" * (new_off - cur))
            sf = src_files[src]
            sf.seek(src_header[src] + old_off)
            remaining = size
            while remaining:
                chunk = sf.read(min(8 * 1024 * 1024, remaining))
                if not chunk:
                    raise SystemExit(f"读取越界: {name.decode()}")
                f.write(chunk)
                remaining -= len(chunk)
            written += size
            cur = new_off + size
    for sf in src_files.values():
        sf.close()
    print(f"完成: {out} = {os.path.getsize(out)/1073741824:.2f}GB (张量数据 {written/1073741824:.2f}GB)")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])

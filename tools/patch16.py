#!/usr/bin/env python3
"""NDM 二进制文案汉化（UTF-16 版）。

原理（实测确认）：
  NDM 从 __cfstring 常量里用 CFStringGetCStringPtr 取到指针后，**按 UTF-16LE 读取**，
  读取单元数取 CFStringGetLength。因此要让界面显示中文，必须：
    * 指针处放 UTF-16LE 数据（BMP 外字符占 2 个单元）
    * length 字段 = UTF-16 单元数
    * flags = 0x7D0（"含非 ASCII 的 UTF-8 常量串"，clang 对非 ASCII 字面量的取值）
  数据写在 load commands 之后的填充区，struct 的 ptr 指过去。
  没有 CFString 结构的串（下载引擎错误描述）就地写 UTF-16LE（放得下才写）。

用法: patch16.py <src> <dst> <JSON...>
"""
import json, os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfstring import analyze, to_bytes, slices, parse


def header_end(data, base):
    ncmds = struct.unpack_from("<I", data, base + 16)[0]
    p = base + 32
    for _ in range(ncmds):
        p += struct.unpack_from("<I", data, p + 4)[0]
    return p


def zero_area(data, base, size, minlen=512):
    h = header_end(data, base)
    m = re.search(rb"\x00{%d,}" % minlen, data[h:base + size])
    if not m:
        return None, 0
    return h + m.start(), m.end() - m.start()


def vm_of(segs, fo):
    for name, vmaddr, vmsize, fileoff, filesize in segs:
        if filesize and fileoff <= fo < fileoff + filesize:
            return vmaddr + (fo - fileoff)
    return None


def u16units(s):
    return len(s.encode("utf-16-le")) // 2


def main(src, dst, tables):
    tr = {}
    for t in tables:
        tr.update(json.load(open(t, encoding="utf-8")))
    # 长的先放，减少碎片
    pairs = sorted(((zh, en) for en, zh in tr.items()), key=lambda kv: -len(kv[0]))

    data = bytearray(open(src, "rb").read())
    _, sl = analyze(src)
    metas = []
    for base, size, cpu in slices(data):
        segs, _ = parse(data, base)
        area, alen = zero_area(data, base, size)
        metas.append((cpu, segs, area, alen))

    stat = {"repoint": 0, "inplace": 0, "skip": 0, "miss": 0}
    for si, s in enumerate(sl):
        if not s:
            continue
        cpu, segs, area, alen = metas[si]
        if area is None:
            print(f"slice{si}: 无可用零区")
            continue
        cur = area & ~1
        limit = area + alen
        print(f"slice{si} cpu={cpu}: 数据区 file=0x{area:x} 可用 {alen} 字节")
        for zh, en in pairs:
            b = to_bytes(en)
            if b not in s["cidx"]:
                stat["miss"] += 1
                continue
            u16 = zh.encode("utf-16-le") + b"\0\0"
            sts = s["structs"].get(b)
            if sts:                                    # 有 CFString：重定向到数据区
                if cur + len(u16) > limit:
                    print(f"   !! 数据区已满（{zh}）")
                    break
                data[cur:cur + len(u16)] = u16
                newvm = vm_of(segs, cur)
                for soff, _, _ in sts:
                    struct.pack_into("<Q", data, soff + 16, newvm)
                    struct.pack_into("<I", data, soff + 8, 0x7D0)
                    struct.pack_into("<Q", data, soff + 24, u16units(zh))
                cur += len(u16)
                stat["repoint"] += 1
            else:                                      # 无 CFString：就地写（放得下才写）
                off = s["cidx"][b]
                cap = len(b) + 1
                if len(u16) <= cap:
                    data[off:off + cap] = u16 + b"\0" * (cap - len(u16))
                    stat["inplace"] += 1
                else:
                    stat["skip"] += 1
        print(f"  累计: 重定向 {stat['repoint']}，就地 {stat['inplace']}，跳过 {stat['skip']}，段内缺失 {stat['miss']}")
    open(dst, "wb").write(bytes(data))
    print("-> 汇总:", stat, "输出", dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])

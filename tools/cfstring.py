#!/usr/bin/env python3
"""Patch NDM's binary strings.

All targets live in __TEXT,__cstring. Two kinds:
  * referenced by a CFString struct in __DATA[_CONST],__cfstring  -> also fix the
    struct's length field (and pointer, when the Chinese needs more room)
  * plain C strings (no CFString struct)                          -> patch bytes only

Overflow (Chinese longer than the original slot) is only possible for CFString-backed
strings: we borrow the unused tail of another translated slot and repoint the struct.

Usage: cfstring.py check|patch <binary>
"""
import struct, sys, json, os
from collections import defaultdict

LC_SEGMENT_64 = 0x19
FAT_MAGIC, FAT_MAGIC_64 = 0xCAFEBABE, 0xCAFEBABF
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(os.path.dirname(HERE), "work")


def slices(data):
    magic = struct.unpack_from(">I", data, 0)[0]
    if magic in (FAT_MAGIC, FAT_MAGIC_64):
        n = struct.unpack_from(">I", data, 4)[0]
        out = []
        for i in range(n):
            cputype, cpusub, off, size, align = struct.unpack_from(">iiIII", data, 8 + i * 20)
            out.append((off, size, cputype))
        return out
    return [(0, len(data), None)]


def parse(data, base):
    ncmds = struct.unpack_from("<I", data, base + 16)[0]
    p, segs, sects = base + 32, [], {}
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack_from("<II", data, p)
        if cmd == LC_SEGMENT_64:
            segname = data[p + 8:p + 24].rstrip(b"\0").decode()
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from("<QQQQ", data, p + 24)
            segs.append((segname, vmaddr, vmsize, fileoff + base, filesize))
            nsects = struct.unpack_from("<I", data, p + 64)[0]
            sp = p + 72
            for _ in range(nsects):
                sn = data[sp:sp + 16].rstrip(b"\0").decode()
                sg = data[sp + 16:sp + 32].rstrip(b"\0").decode()
                addr, size = struct.unpack_from("<QQ", data, sp + 32)
                off = struct.unpack_from("<I", data, sp + 48)[0]
                sects[(sg, sn)] = (off + base, size, addr)
                sp += 80
        p += cmdsize
    return segs, sects


def vm2file(segs, vm):
    for name, vmaddr, vmsize, fileoff, filesize in segs:
        if filesize and vmaddr <= vm < vmaddr + vmsize:
            return fileoff + (vm - vmaddr)
    return None


def cstrings(data, off, size):
    """{bytes: file_offset} for every NUL-terminated string in the section."""
    out = {}
    p, end = off, off + size
    while p < end:
        q = data.find(b"\0", p, end)
        if q < 0:
            break
        if q > p:
            out.setdefault(data[p:q], p)
        p = q + 1
    return out


def analyze(binary):
    data = open(binary, "rb").read()
    res = []
    for base, size, cpu in slices(data):
        segs, sects = parse(data, base)
        cs = sects.get(("__TEXT", "__cstring"))
        fs = sects.get(("__DATA", "__cfstring")) or sects.get(("__DATA_CONST", "__cfstring"))
        if not cs:
            res.append(None)
            continue
        co, csz, caddr = cs
        cidx = cstrings(data, co, csz)
        structs = defaultdict(list)      # bytes -> [(struct_file_off, ptr_file, length)]
        if fs:
            fo, fsz, faddr = fs
            for i in range(0, fsz, 32):
                isa, flags, ptr, length = struct.unpack_from("<QQQQ", data, fo + i)
                if not ptr or not length:
                    continue
                pfo = vm2file(segs, ptr)
                if pfo is None or not (co <= pfo < co + csz):
                    continue
                b = data[pfo:pfo + length]
                structs[b].append((fo + i, pfo, length))
        res.append({"cpu": cpu, "cstring": (co, csz, caddr), "cf": (fs or (0, 0, 0)),
                    "cidx": cidx, "structs": structs})
    return data, res


def to_bytes(s):
    """译文 -> 字节。默认 UTF-8；'RAW:' 前缀表示按 latin-1 落盘原始字节（实验用）。"""
    if isinstance(s, str) and s.startswith("RAW:"):
        return s[4:].encode("latin-1")
    return s.encode()


# clang 的常量串规则：
#   纯 ASCII      -> flags 0x7C8（8 位），length = 字节数
#   含非 ASCII    -> flags 0x7D0（UTF-8），length = 字符数
ASCII_FLAGS, UTF8_FLAGS = 0x7C8, 0x7D0

# 实验用：强制这些译文用字节数作为 length（默认按 clang 语义用字符数）
FORCE_BYTE_LEN = set()


def fix_struct(data, soff, nb, length=None):
    """把 struct 的 flags 与 length 调成与内容一致。

    length=None 时按 clang 语义自动取字符数；显式传入则用给定值（实验用）。
    """
    try:
        chars = len(nb.decode("utf-8"))
    except UnicodeDecodeError:
        chars = len(nb)
    ascii_only = all(b < 128 for b in nb)
    if length is None:
        length = len(nb) if nb in FORCE_BYTE_LEN else chars
    struct.pack_into("<I", data, soff + 8, ASCII_FLAGS if ascii_only else UTF8_FLAGS)
    struct.pack_into("<Q", data, soff + 24, length)


def run(binary, inplace, overflow, apply_changes):
    data, sl = analyze(binary)
    if apply_changes:
        data = bytearray(data)
    rep = []
    for s in sl:
        if not s:
            continue
        free = []
        for src, dst in inplace.items():
            b, nb = to_bytes(src), to_bytes(dst)
            if b not in s["cidx"]:
                rep.append(("MISS", src, dst, "段内没有"))
                continue
            if len(nb) > len(b):
                rep.append(("TOOLONG", src, dst, f"{len(nb)}>{len(b)}"))
                continue
            off = s["cidx"][b]
            if apply_changes:
                data[off:off + len(b)] = nb + b"\0" * (len(b) - len(nb))
                for soff, _, _ in s["structs"].get(b, []):
                    fix_struct(data, soff, nb)
            if len(b) - len(nb) >= 2:
                # 留 1 字节给原串自己的 C 终止符，剩余才可借出
                free.append([off + len(nb) + 1, len(b) - len(nb) - 1])
            rep.append(("OK", src, dst, f"{len(b)}->{len(nb)}"))
        for src, dst in sorted(overflow.items(), key=lambda kv: -len(to_bytes(kv[1]))):
            b, nb = to_bytes(src), to_bytes(dst)
            if b not in s["cidx"]:
                rep.append(("MISS", src, dst, "段内没有"))
                continue
            off = s["cidx"][b]
            if len(nb) <= len(b):
                if apply_changes:
                    data[off:off + len(b)] = nb + b"\0" * (len(b) - len(nb))
                    for soff, _, _ in s["structs"].get(b, []):
                        fix_struct(data, soff, nb)
                rep.append(("FITS", src, dst, "其实可原地放"))
                continue
            if b not in s["structs"]:
                rep.append(("NOPTR", src, dst, "非 CFString，无法重定向"))
                continue
            need = len(nb) + 1
            slot = next((f for f in free if f[1] >= need), None)
            if not slot:
                rep.append(("NOSPACE", src, dst, f"需要 {need}"))
                continue
            free.remove(slot)
            if apply_changes:
                data[slot[0]:slot[0] + need] = nb + b"\0"
                newvm = s["cstring"][2] + (slot[0] - s["cstring"][0])
                for soff, _, _ in s["structs"][b]:
                    struct.pack_into("<Q", data, soff + 16, newvm)
                    fix_struct(data, soff, nb)
            rep.append(("RELOC", src, dst, f"{len(b)}->{len(nb)}"))
    if apply_changes:
        open(binary, "wb").write(bytes(data))
    ok = sum(1 for r in rep if r[0] == "OK")
    bad = [r for r in rep if r[0] not in ("OK",)]
    for st, src, dst, extra in bad:
        print(f"  {st:8s} {src!r} -> {dst!r}  {extra}")
    print(f"# 原地 {ok} 条，其它 {len(bad)} 条（每切片）")


if __name__ == "__main__":
    ip = json.load(open(os.path.join(WORK, "translations_bin.json"), encoding="utf-8"))
    ovp = os.path.join(WORK, "translations_bin_overflow.json")
    ov = json.load(open(ovp, encoding="utf-8")) if os.path.exists(ovp) else {}
    run(sys.argv[2], ip, ov, sys.argv[1] == "patch")

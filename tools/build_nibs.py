#!/usr/bin/env python3
"""Build zh-Hans.lproj nibs for NeatDownloadManager, from the USER'S OWN installed copy.

This script contains NO copyrighted material. It reads the nib files shipped with the
user's installed NeatDownloadManager.app and replaces only user-visible string *values*
with Chinese, using the translation table in ../translations/nib.json (our own work).

Replaced value positions:
  NS.string, NSContents, NSTitle, NSToolTip, NSAlternateTitle,
  and any key/property ending in .title / .label / .paletteLabel / .headerCell.title /
  .toolTip / .alternateTitle.
Dictionary keys and identifiers (class names, keyPaths, action names) are never touched.

Usage: python3 build_nibs.py
Output: ../build/zh-Hans.lproj  (then install.sh copies it into the app)
"""
import plistlib, os, sys, json, shutil, glob

APP = "/Applications/NeatDownloadManager.app"
RES = os.path.join(APP, "Contents", "Resources")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "build", "zh-Hans.lproj")
TR = json.load(open(os.path.join(ROOT, "translations", "nib.json"), encoding="utf-8"))

EXACT_KEYS = {"NS.string", "NSContents", "NSTitle", "NSToolTip", "NSAlternateTitle"}
SUFFIX_KEYS = (".title", ".label", ".paletteLabel", ".headerCell.title", ".toolTip", ".alternateTitle")

stats = {"files": 0, "hits": 0}
missed = {}
hit_log = {}


def translate_dict(d, rel, log):
    for k, v in list(d.items()):
        if isinstance(v, str) and isinstance(k, str) and (k in EXACT_KEYS or k.endswith(SUFFIX_KEYS)):
            if v in TR:
                d[k] = TR[v]
                stats["hits"] += 1
                log.append((rel, k, v, TR[v]))
            elif v.strip() and v not in ("$null",):
                missed.setdefault(v, set()).add(rel)
        elif isinstance(v, (dict, list)):
            walk(v, rel, log)


# 老式 nib 里作为「裸字符串」出现的 UI 文案
BARE_OK = set(TR.keys())


def translate_list(lst, rel, log):
    for i, v in enumerate(lst):
        if isinstance(v, str):
            if v in BARE_OK and v.strip():
                lst[i] = TR[v]
                stats["hits"] += 1
                log.append((rel, f"$objects[{i}]", v, TR[v]))
        elif isinstance(v, (dict, list)):
            walk(v, rel, log)


def walk(o, rel, log):
    if isinstance(o, dict):
        translate_dict(o, rel, log)
    elif isinstance(o, list):
        translate_list(o, rel, log)


def build(src, rel_out):
    with open(src, "rb") as f:
        pl = plistlib.load(f)
    log = []
    walk(pl, rel_out, log)
    dst = os.path.join(OUT, rel_out)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        plistlib.dump(pl, f, fmt=plistlib.FMT_BINARY)
    stats["files"] += 1
    hit_log[rel_out] = log
    return len(log)


if __name__ == "__main__":
    if not os.path.isdir(APP):
        sys.exit(f"找不到 {APP}，请先安装 NeatDownloadManager 1.3")
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    # 1) 老式 nib（Resources 根目录，单文件）
    for f in sorted(glob.glob(os.path.join(RES, "*.nib"))):
        if os.path.isfile(f):
            n = build(f, os.path.basename(f))
            print(f"{n:3d} 条  {os.path.basename(f)}")

    # 2) 目录型 nib（含 keyedobjects*.nib），Base.lproj 的提升为 zh-Hans 顶层
    for d in sorted(glob.glob(os.path.join(RES, "*.nib")) + glob.glob(os.path.join(RES, "Base.lproj", "*.nib"))):
        if not os.path.isdir(d):
            continue
        rel = os.path.relpath(d, RES)
        rel = rel.replace("Base.lproj/", "")
        total = 0
        for inner in sorted(os.listdir(d)):
            if inner.startswith("keyedobjects"):
                total += build(os.path.join(d, inner), os.path.join(rel, inner))
        print(f"{total:3d} 条  {rel}/  (目录型)")

    json.dump(hit_log, open(os.path.join(OUT, "nib_hits.json"), "w"), ensure_ascii=False, indent=1)
    print(f"\n# 生成 {stats['files']} 个文件，替换 {stats['hits']} 处")
    print("\n# 未命中的可见字符串（可能是漏译，需人工确认）:")
    for s in sorted(missed):
        if len(s) >= 3 and not s.startswith(("{{", "T@", "NS", "com.", "dyn.")):
            print(f"   {s!r}   <- {sorted(missed[s])}")

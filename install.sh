#!/bin/bash
# NeatDownloadManager 中文汉化安装器（仅使用你本机已安装的 NeatDownloadManager.app）。
# 仓库本身不含任何原程序文件；所有汉化资源都在你本机安装时即时生成。
#
# 用法: ./install.sh [--no-launch]
set -u
REPO="$(cd "$(dirname "$0")" && pwd)"
APP=/Applications/NeatDownloadManager.app
BIN="$APP/Contents/MacOS/NeatDownloadManager"
RES="$APP/Contents/Resources"
BACKUP="$HOME/Library/Application Support/NeatDownloadManager-zh-backup"
LAUNCH=1
for a in "$@"; do [ "$a" = "--no-launch" ] && LAUNCH=0; done

# 中文图标别名：原始英文名 -> 中文名（imageNamed 用的是分类名，翻译标签后需按中文名查找）
ICONS=(
  "all downloads.png:全部下载.png"
  "video.png:视频.png"
  "audio.png:音频.png"
  "compressed.png:压缩包.png"
  "complete.png:完成.png"
  "incomplete.png:未完成.png"
  "document.png:文档.png"
  "misc.png:其他.png"
  "delete.png:删除.png"
  "about.png:关于.png"
  "options.png:选项.png"
  "options.png:设置.png"
  "Pause.png:暂停.png"
  "Resume.png:继续.png"
  "Newurl.png:新建链接.png"
  "quit.png:完全退出.png"
)

need() { command -v "$1" >/dev/null 2>&1 || { echo "!! 需要 $1，请先安装"; exit 1; }; }
need python3

if [ ! -d "$APP" ]; then echo "!! 找不到 $APP，请先安装 NeatDownloadManager 1.3"; exit 1; fi

echo "== 1) 退出 NDM =="
if pgrep -x NeatDownloadManager >/dev/null 2>&1; then
  osascript -e 'quit app "NeatDownloadManager"' >/dev/null 2>&1
  for i in $(seq 1 20); do pgrep -x NeatDownloadManager >/dev/null 2>&1 || break; sleep 0.5; done
  pgrep -x NeatDownloadManager >/dev/null 2>&1 && { pkill -x NeatDownloadManager; sleep 1; }
  echo "已退出"
else
  echo "本来就没在运行"
fi

echo "== 2) 备份原版主程序 =="
mkdir -p "$BACKUP"
if [ ! -f "$BACKUP/NeatDownloadManager.orig" ]; then
  cp "$BIN" "$BACKUP/NeatDownloadManager.orig"
  echo "  已备份到 $BACKUP/NeatDownloadManager.orig"
else
  echo "  备份已存在，跳过"
fi

echo "== 3) 汉化二进制（UTF-16LE 重定向）=="
rm -rf "$REPO/build"
mkdir -p "$REPO/build"
python3 "$REPO/tools/patch16.py" "$BIN" "$REPO/build/NeatDownloadManager" \
  "$REPO/translations/binary.json" "$REPO/translations/binary_overflow.json" | tail -3
cp "$REPO/build/NeatDownloadManager" "$BIN"
chmod 755 "$BIN"
echo "  已替换主程序"

echo "== 4) 生成并安装 zh-Hans.lproj（nib 文案）=="
python3 "$REPO/tools/build_nibs.py" | tail -3
rm -rf "$RES/zh-Hans.lproj"
ditto "$REPO/build/zh-Hans.lproj" "$RES/zh-Hans.lproj"
find "$RES/zh-Hans.lproj" -type f | wc -l | xargs echo "  文件数:"

echo "== 5) 生成并安装中文图标别名 =="
mkdir -p "$REPO/build/中文图标"
for e in "${ICONS[@]}"; do
  src="${e%%:*}"; dst="${e##*:}"
  if [ -f "$RES/$src" ]; then
    cp "$RES/$src" "$REPO/build/中文图标/$dst"
    cp "$REPO/build/中文图标/$dst" "$RES/$dst"
  else
    echo "  ! 原图标缺失: $src（跳过 $dst）"
  fi
done
ls "$REPO/build/中文图标" | wc -l | xargs echo "  中文图标数:"

echo "== 6) 重签（ad-hoc）=="
codesign --force --sign - "$APP/Contents/PlugIns/NeatDownloadManager Extension.appex" 2>&1 | tail -1
codesign --force --sign - "$APP" 2>&1 | tail -1
codesign -v "$APP" >/dev/null 2>&1 && echo "  签名有效" || echo "  !! 签名校验失败"

echo "== 7) 去掉隔离属性 =="
xattr -dr com.apple.quarantine "$APP" 2>/dev/null; echo "  完成"

if [ "$LAUNCH" = "1" ]; then
  echo "== 8) 启动 =="
  open -a "$APP"
  sleep 3
  pgrep -x NeatDownloadManager >/dev/null 2>&1 && echo "  已启动 (pid $(pgrep -x NeatDownloadManager))" || echo "  !! 未启动"
fi
echo "完成。"

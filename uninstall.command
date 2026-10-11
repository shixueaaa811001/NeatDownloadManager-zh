#!/bin/bash
# 还原 NeatDownloadManager 到英文原版（从安装时在本机创建的备份恢复）。
# 用法: ./uninstall.command   （或直接 ./install.sh 不成，用本文件）
set -u
REPO="$(cd "$(dirname "$0")" && pwd)"
APP=/Applications/NeatDownloadManager.app
BIN="$APP/Contents/MacOS/NeatDownloadManager"
RES="$APP/Contents/Resources"
BACKUP="$HOME/Library/Application Support/NeatDownloadManager-zh-backup"

ICONS=(
  "全部下载.png" "视频.png" "音频.png" "压缩包.png" "完成.png" "未完成.png"
  "文档.png" "其他.png" "删除.png" "关于.png" "选项.png" "设置.png"
  "暂停.png" "继续.png" "新建链接.png" "完全退出.png"
)

echo "== 退出 NDM =="
if pgrep -x NeatDownloadManager >/dev/null 2>&1; then
  osascript -e 'quit app "NeatDownloadManager"' >/dev/null 2>&1
  for i in $(seq 1 20); do pgrep -x NeatDownloadManager >/dev/null 2>&1 || break; sleep 0.5; done
  echo "已退出"
else echo "本来就没在运行"; fi

if [ ! -f "$BACKUP/NeatDownloadManager.orig" ]; then
  echo "!! 未找到备份（$BACKUP），无法还原二进制。仅清理汉化资源。"
else
  cp "$BACKUP/NeatDownloadManager.orig" "$BIN"
  chmod 755 "$BIN"
  echo "  已还原主程序"
fi

echo "== 删除汉化资源 =="
rm -rf "$RES/zh-Hans.lproj"
for n in "${ICONS[@]}"; do rm -f "$RES/$n"; done
echo "  已删除 zh-Hans.lproj 与中文图标"

echo "== 重签 =="
codesign --force --sign - "$APP/Contents/PlugIns/NeatDownloadManager Extension.appex" 2>&1 | tail -1
codesign --force --sign - "$APP" 2>&1 | tail -1
codesign -v "$APP" >/dev/null 2>&1 && echo "  签名有效" || echo "  !! 签名校验失败"
echo "已还原为英文原版。"

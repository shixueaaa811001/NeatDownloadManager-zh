# NeatDownloadManager 中文汉化（macOS）

纯脚本 + 翻译表的 NeatDownloadManager 1.3 汉化方案。**仓库不含任何原程序文件**，
所有汉化资源都在你本机安装时，从你已安装的 NeatDownloadManager.app 现场生成。

## 法律声明（必读）

NeatDownloadManager 的版权归原作者 **Javad Motallebi** 所有
（`Info.plist` 写明 `Copyright © 2021 Javad Motallebi. All rights reserved.`）。

本仓库只分发：

- 汉化脚本（`tools/*.py`、`install.sh`）
- 翻译表（`translations/*.json`，由贡献者编写的 `{英文: 中文}` 映射）

安装时脚本读取**你本机已安装**的 NeatDownloadManager 程序，就地生成中文资源，
不复制、不重新分发任何原程序二进制或资源。

> ⚠️ **请勿**在 GitHub Release 中附带修改后的二进制或原程序文件；只分享本仓库源码即可。
> 这样既能让大家使用，也不触碰原作者的版权红线。

## 支持版本

- **NeatDownloadManager 1.3**（macOS）
- 二进制翻译按**字符串内容**匹配，其他版本字符串不同则可能不匹配。

## 使用方法

```bash
git clone <本仓库地址>
cd NeatDownloadManager-zh
# 推荐：双击 install.command（在 Finder 里双击即可）
# 或终端执行：
./install.sh
```

要求本机已安装 NeatDownloadManager 1.3（位于 `/Applications/NeatDownloadManager.app`），
且装有 Python 3。安装器会：退出 NDM → 备份原版主程序到
`~/Library/Application Support/NeatDownloadManager-zh-backup/` → 汉化二进制 →
生成并安装 `zh-Hans.lproj` → 生成中文图标别名 → ad-hoc 重签 → 去隔离 → 启动。

## 卸载

双击 `uninstall.command`（或 `./uninstall.command`），会从备份还原主程序并删除汉化资源，
回到英文原版。

## 工作原理

1. **二进制文案（UTF-16LE 重定向）**：NDM 取 `CFString` 指针后按 UTF-16LE 读取，
   故译文以 UTF-16LE 写入 load commands 后的填充区，并重设 `ptr`/`length`/`flags`。
   无 CFString 结构的串就地改写为 UTF-16LE。`tools/patch16.py` 按英文原文匹配替换。
2. **nib 文案**：`tools/build_nibs.py` 读取你已装的 nib，只替换用户可见的字符串值
   （标题、标签、提示等），不动类名 / keyPath / action 等标识符，写入 `zh-Hans.lproj`。
3. **图标**：`[NSImage imageNamed:]` 以分类名查找图标，翻译标签后需按中文名查找，
   安装器把原图标复制为中文名别名放入 `Resources/`。

## 已知限制

- 约 10 条 FTP 调试提示、窗口标题 `Neat Download Manager 1.3` 保留英文。
- 标准按钮 `OK` 保留英文（未做强制替换）。

## 参考

- [hardwin2023/NeatDownloadManager-zh](https://github.com/hardwin2023/NeatDownloadManager-zh)（macOS，nib 层）
- [qiqi258/NeatDownloadManager-zh](https://github.com/qiqi258/NeatDownloadManager-zh)（Windows，纯脚本）

本方案在它们基础上做到了二进制层 UTF-16 汉化与图标别名恢复。

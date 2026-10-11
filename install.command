#!/bin/bash
# 双击运行：在本仓库目录内执行安装器。
cd "$(dirname "$0")" || exit 1
exec ./install.sh "$@"

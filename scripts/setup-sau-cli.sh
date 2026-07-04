#!/usr/bin/env bash
# 用途：把同级的 social-auto-upload 仓库以可编辑模式装进当前 Python 环境，暴露 `sau` CLI。
# 使用场景：
#   1. 本机（非 Docker）worker：直接在 Backend 虚拟环境里执行本脚本。
#   2. Docker worker 容器：`docker compose exec worker bash /app/../scripts/setup-sau-cli.sh`
#      （需要先给 worker 服务加一条把 ../social-auto-upload 挂进容器的 volume）。
# 安装完成后需要设置 ENABLE_DISTRIBUTION=true，并在 social-auto-upload/conf.py 中完成对应平台登录态配置，
# 详见 social-auto-upload 项目自身文档；`sau` 依赖 opencv-python，Debian/Ubuntu 精简镜像可能还需要
# `apt-get install -y libgl1 libglib2.0-0`。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAU_REPO="${1:-$SCRIPT_DIR/../../social-auto-upload}"

if [ ! -f "$SAU_REPO/pyproject.toml" ]; then
  echo "未找到 social-auto-upload 仓库：$SAU_REPO" >&2
  echo "用法：$0 [social-auto-upload 仓库路径]" >&2
  exit 1
fi

echo "以可编辑模式安装 sau CLI，来源：$SAU_REPO"
pip install --no-cache-dir -e "$SAU_REPO"

echo "校验 sau 命令："
sau --help >/dev/null && echo "sau CLI 安装成功。"

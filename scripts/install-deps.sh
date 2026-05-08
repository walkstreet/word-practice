#!/usr/bin/env bash
# 安装后端 Python（venv）与前端 npm 依赖。
# Unix/macOS/Linux 直接用本脚本；Windows 原生请改用 scripts/install-deps.ps1（或 Git Bash）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"

if [[ ! -d backend/.venv ]]; then
  "$PY" -m venv backend/.venv
fi

# shellcheck disable=SC1091
source backend/.venv/bin/activate
pip install -U pip
pip install -r backend/requirements.txt
deactivate

(cd frontend && npm ci)

echo "依赖已装好。后端 venv：backend/.venv；生产启动：./scripts/start-prod.sh"

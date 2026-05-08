#!/usr/bin/env bash
# 以前端构建产物（Vite preview）+ uvicorn 方式启动前后端生产模式。
# 需在仓库根目录执行；请先运行 scripts/install-deps.sh。
# Windows 原生请改用 scripts/start-prod.ps1（或 Git Bash 跑本脚本）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACK_PORT="${BACKEND_PORT:-3000}"
FRONT_PORT="${FRONTEND_PORT:-5173}"
BIND_HOST="${BIND_HOST:-0.0.0.0}"

cd "$ROOT"

if [[ ! -d backend/.venv ]]; then
  echo "未找到 backend/.venv，请先执行：scripts/install-deps.sh" >&2
  exit 1
fi

if [[ ! -d frontend/node_modules ]]; then
  echo "未找到 frontend/node_modules，请先执行：scripts/install-deps.sh" >&2
  exit 1
fi

(cd frontend && npm run build)

cleanup() {
  if [[ -n "${BACK_PID:-}" ]]; then
    kill "$BACK_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONT_PID:-}" ]]; then
    kill "$FRONT_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "后端 http://127.0.0.1:${BACK_PORT}（局域网可改用本机 IP）"
echo "前端 http://127.0.0.1:${FRONT_PORT}"
echo "生产构建下 API 默认指向 http://127.0.0.1:${BACK_PORT}/api；若从其他机器访问前端，请先设 VITE_API_BASE_URL 后重新 npm run build，见 frontend/src/api.ts"

(
  cd "$ROOT/backend"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  exec uvicorn app.main:app --host "$BIND_HOST" --port "$BACK_PORT"
) &
BACK_PID=$!

sleep 1

(
  cd "$ROOT/frontend"
  exec npm run preview -- --host "$BIND_HOST" --port "$FRONT_PORT"
) &
FRONT_PID=$!

wait $BACK_PID $FRONT_PID

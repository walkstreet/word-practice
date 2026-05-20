#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "用法: ./scripts/migrate-old-data.sh <旧word_practice.db路径> [源用户名=admin] [目标用户名=admin]"
  echo "示例: ./scripts/migrate-old-data.sh \"/Users/me/Downloads/word_practice.db\""
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE_DB="$1"
SOURCE_USER="${2:-admin}"
TARGET_USER="${3:-admin}"

if [[ ! -f "$SOURCE_DB" ]]; then
  echo "错误: 找不到旧数据库文件: $SOURCE_DB"
  exit 1
fi

PYTHON_BIN="${ROOT_DIR}/backend/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

cd "${ROOT_DIR}/backend"
"$PYTHON_BIN" -m app.migrate_external_user_data \
  --source-db "$SOURCE_DB" \
  --source-username "$SOURCE_USER" \
  --target-username "$TARGET_USER"

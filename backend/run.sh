#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

if [[ ! -f ".env" ]]; then
  echo "未找到 .env，请先执行: cp .env.example .env"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source ".env"
set +a

SERVER_HOST="${SERVER_HOST:-0.0.0.0}"
SERVER_PORT="${SERVER_PORT:-3005}"
APP_MODULE="${APP_MODULE:-app.main:app}"

PYTHON_BIN=""
if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "未找到可用 Python，请先安装 Python 3.11+"
  exit 1
fi

if [[ -x ".venv/bin/uvicorn" ]]; then
  exec ".venv/bin/uvicorn" "${APP_MODULE}" --host "${SERVER_HOST}" --port "${SERVER_PORT}"
fi

if "${PYTHON_BIN}" -c "import uvicorn" >/dev/null 2>&1; then
  exec "${PYTHON_BIN}" -m uvicorn "${APP_MODULE}" --host "${SERVER_HOST}" --port "${SERVER_PORT}"
fi

if command -v uvicorn >/dev/null 2>&1; then
  exec uvicorn "${APP_MODULE}" --host "${SERVER_HOST}" --port "${SERVER_PORT}"
fi

echo "未找到 uvicorn，请先安装依赖（例如: pip install -e .[dev]）"
exit 1

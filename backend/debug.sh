#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

if [[ ! -f ".env" ]]; then
  echo "未找到 .env，请先执行: cp .env.example .env"
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "未找到 curl，请先安装 curl"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source ".env"
set +a

SERVER_HOST="${SERVER_HOST:-0.0.0.0}"
SERVER_PORT="${SERVER_PORT:-3005}"
LOCAL_BASE_URL="${DEBUG_BASE_URL:-http://127.0.0.1:${SERVER_PORT}}"
WAIT_CLIENTS_SECONDS="${DEBUG_WAIT_CLIENTS_SECONDS:-30}"
WAIT_CLIENTS="${DEBUG_WAIT_CLIENTS:-true}"

echo "[debug] 启动服务..."
"${SCRIPT_DIR}/run_server.sh" &
SERVER_PID=$!

cleanup() {
  if kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "[debug] 等待服务就绪: ${LOCAL_BASE_URL}/healthz"
for _ in {1..40}; do
  if curl -fsS "${LOCAL_BASE_URL}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "${LOCAL_BASE_URL}/healthz" >/dev/null 2>&1; then
  echo "[debug] 服务未就绪，退出"
  exit 1
fi

if [[ "${WAIT_CLIENTS}" == "true" ]]; then
  echo "[debug] 等待客户端连接（最多 ${WAIT_CLIENTS_SECONDS}s）..."
  for ((i=1; i<=WAIT_CLIENTS_SECONDS; i++)); do
    STATUS_JSON="$(curl -fsS "${LOCAL_BASE_URL}/v1/debug/status" 2>/dev/null || true)"
    if [[ -n "${STATUS_JSON}" ]] && [[ "${STATUS_JSON}" != *"\"online_clients\":0"* ]]; then
      echo "[debug] 检测到在线客户端，开始调试检查"
      break
    fi
    sleep 1
  done
fi

DEBUG_URL="${LOCAL_BASE_URL}/v1/debug/run"
if [[ -n "${DEBUG_CLIENT_ID:-}" ]]; then
  DEBUG_URL="${DEBUG_URL}?client_id=${DEBUG_CLIENT_ID}"
fi

echo "[debug] 触发调试检查: ${DEBUG_URL}"
DEBUG_RESPONSE="$(curl -fsS -X POST "${DEBUG_URL}")"
echo "[debug] 调试结果:"
echo "${DEBUG_RESPONSE}"

echo "[debug] 服务保持运行中，按 Ctrl+C 结束。"
wait "${SERVER_PID}"

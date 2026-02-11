#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${REPO_DIR}"

if [[ ! -d ".git" ]]; then
  echo "当前目录不是 Git 仓库: ${REPO_DIR}"
  exit 1
fi

BRANCH="${UPDATE_BRANCH:-main}"
REMOTE="${UPDATE_REMOTE:-origin}"
TARGET="${REMOTE}/${BRANCH}"

echo "[update] 强制同步分支: ${TARGET}"
echo "[update] 将覆盖本地未提交改动并删除未跟踪文件"
git fetch "${REMOTE}" "${BRANCH}"
git reset --hard "${TARGET}"
git clean -fd

echo "[update] 更新完成，当前版本:"
git --no-pager log -1 --oneline

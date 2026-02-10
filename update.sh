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

echo "[update] 拉取远端分支: ${REMOTE}/${BRANCH}"
git fetch "${REMOTE}" "${BRANCH}"
git pull --ff-only "${REMOTE}" "${BRANCH}"

echo "[update] 更新完成"

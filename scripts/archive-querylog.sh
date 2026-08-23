#!/usr/bin/env bash
#
# archive-querylog.sh
# 每天 4 点由 cron 调用：
#   1) 将 AdGuard Home 的 querylog.json 归档到 /root/adguardhome/，
#      按「前一天日期」命名，例如 2026-08-22-querylog.json
#   2) 将该文件推送到 GitHub 仓库 vin199306/adguardhome-blocklist
#
# 依赖：bash、coreutils(date/base64/stat)、git、curl
# 认证：GitHub PAT（环境变量 GITHUB_TOKEN 或文件 /root/adguardhome/.github_token）
#
set -euo pipefail

# ============================ 配置 ============================
SRC_FILE="/var/lib/adguardhome/data/querylog.json"
DEST_DIR="/root/adguardhome"
REPO="vin199306/adguardhome-blocklist"      # owner/repo
BRANCH="main"

# GitHub PAT：环境变量优先，其次读密钥文件
if [ -n "${GITHUB_TOKEN:-}" ]; then
  TOKEN="$GITHUB_TOKEN"
elif [ -f "$DEST_DIR/.github_token" ]; then
  TOKEN="$(cat "$DEST_DIR/.github_token")"
else
  TOKEN=""
fi

LOG_FILE="$DEST_DIR/archive.log"
REMOTE_URL="https://github.com/$REPO.git"
AUTH_URL="https://$TOKEN@github.com/$REPO.git"   # 含 token 的推送地址

# ============================ 函数 ============================
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# ============================ 主流程 ============================
mkdir -p "$DEST_DIR"

# 前一天日期（脚本在 4 点跑，日志归属前一天）
YESTERDAY="$(date -d yesterday +%Y-%m-%d)"
DEST_FILE="$DEST_DIR/$YESTERDAY-querylog.json"
REMOTE_NAME="$YESTERDAY-querylog.json"

if [ ! -f "$SRC_FILE" ]; then
  log "ERROR: 源文件不存在: $SRC_FILE（可能已归档或 AGH 路径不同）"
  exit 1
fi

# 1) 移动并以前一天日期命名
#    注意：mv 后 AGH 会在下一次写入时重建 querylog.json。
#    若你的 AGH 持有文件句柄导致重建异常，可把下面这行改为 cp。
mv "$SRC_FILE" "$DEST_FILE"
log "已归档: $DEST_FILE ($(du -h "$DEST_FILE" | cut -f1))"

# 2) 上传到 GitHub
if [ -z "$TOKEN" ]; then
  log "WARN: 未配置 GITHUB_TOKEN，已跳过上传"
  exit 0
fi

WORK_DIR="$DEST_DIR/repo"
if [ ! -d "$WORK_DIR/.git" ]; then
  log "首次运行：克隆仓库到 $WORK_DIR"
  rm -rf "$WORK_DIR"
  git clone --depth 1 "$AUTH_URL" "$WORK_DIR"
else
  log "拉取最新变更"
  git -C "$WORK_DIR" pull --rebase "$AUTH_URL" "$BRANCH"
fi

cp "$DEST_FILE" "$WORK_DIR/$REMOTE_NAME"
git -C "$WORK_DIR" add "$REMOTE_NAME"

if git -C "$WORK_DIR" diff --cached --quiet; then
  log "远程已存在相同内容，跳过提交"
else
  git -C "$WORK_DIR" -c user.name="adguard-archiver" -c user.email="archiver@local" \
    commit -m "archive querylog $YESTERDAY"
  git -C "$WORK_DIR" push "$AUTH_URL" "$BRANCH"
  log "已上传 $REMOTE_NAME 到 GitHub ($REPO)"
fi

log "完成"

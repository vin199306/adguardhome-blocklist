#!/bin/sh
#
# archive-querylog.sh  —— 适用于 OpenStick / BusyBox 等精简 Linux
# 每天 4 点由 cron 调用：
#   1) 把 AdGuard Home 的 querylog.json 归档到 /root/adguardhome/，
#      按「前一天日期」命名，例如 2026-08-22-querylog.json
#   2) 通过 GitHub git-data API 上传到 vin199306/adguardhome-blocklist
#       （不依赖 git/curl，用设备自带的 python3；支持大文件）
#
set -e

SRC="/var/lib/adguardhome/data/querylog.json"
DEST_DIR="/root/adguardhome"
REPO="vin199306/adguardhome-blocklist"
BRANCH="main"
TOKEN_FILE="$DEST_DIR/.github_token"
LOG="$DEST_DIR/archive.log"

log() { echo "[$(date +%Y-%m-%d_%H:%M:%S)] $*" | tee -a "$LOG"; }

mkdir -p "$DEST_DIR"

# 前一天日期（BusyBox date 不支持 -d，改用 python3）
YESTERDAY=$(python3 -c "import datetime;print((datetime.date.today()-datetime.timedelta(days=1)).strftime('%Y-%m-%d'))")
DEST="$DEST_DIR/$YESTERDAY-querylog.json"
REMOTE="$YESTERDAY-querylog.json"

if [ ! -f "$SRC" ]; then
  log "ERROR: 源文件不存在: $SRC"
  exit 1
fi

# 1) 移动并以前一天日期命名
#    mv 后 AGH 会在下次写入时重建 querylog.json。
#    若 AGH 持有句柄导致异常，可把下面这行改成 cp。
mv "$SRC" "$DEST"
log "已归档: $DEST ($(du -h "$DEST" | cut -f1))"

# 2) 读取 GitHub PAT（环境变量优先，其次密钥文件）
TOKEN="${GITHUB_TOKEN:-}"
if [ -z "$TOKEN" ] && [ -f "$TOKEN_FILE" ]; then
  TOKEN=$(cat "$TOKEN_FILE" | tr -d '[:space:]')
fi

if [ -z "$TOKEN" ]; then
  log "WARN: 未配置 GITHUB_TOKEN，跳过上传"
  exit 0
fi

export GITHUB_TOKEN="$TOKEN"
export GH_REPO="$REPO"
export GH_BRANCH="$BRANCH"
export GH_REMOTE="$REMOTE"
export GH_LOCAL="$DEST"

log "开始上传 $REMOTE 到 GitHub ..."
python3 - <<'PYEOF'
import os, sys, base64, json, urllib.request, urllib.error

API = "https://api.github.com"
repo = os.environ["GH_REPO"]
branch = os.environ["GH_BRANCH"]
remote = os.environ["GH_REMOTE"]
local = os.environ["GH_LOCAL"]
token = os.environ["GITHUB_TOKEN"]
auth = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json"}

def req(method, url, data=None):
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, method=method, headers=auth)
    try:
        with urllib.request.urlopen(r, timeout=300) as resp:
            return resp.read().decode()
    except urllib.error.HTTPError as e:
        sys.stderr.write("HTTP %s: %s\n" % (e.code, e.read().decode()[:800]))
        raise

# 1) 创建 blob（支持大文件，上限 100MB）
with open(local, "rb") as f:
    content = base64.b64encode(f.read()).decode()
blob_sha = json.loads(req("POST", f"{API}/repos/{repo}/git/blobs",
                          {"content": content, "encoding": "base64"}))["sha"]

# 2) 取当前分支最新提交 -> 基树
ref = json.loads(req("GET", f"{API}/repos/{repo}/git/refs/heads/{branch}"))
commit_sha = ref["object"]["sha"]
base_tree = json.loads(req("GET", f"{API}/repos/{repo}/git/commits/{commit_sha}"))["tree"]["sha"]

# 3) 创建新树（以基树为底，覆盖/新增该文件）
tree_sha = json.loads(req("POST", f"{API}/repos/{repo}/git/trees",
                         {"base_tree": base_tree,
                          "tree": [{"path": remote, "mode": "100644",
                                    "type": "blob", "sha": blob_sha}]}))["sha"]

# 4) 创建提交
new_commit = json.loads(req("POST", f"{API}/repos/{repo}/git/commits",
                            {"message": "archive querylog " + remote,
                             "tree": tree_sha, "parents": [commit_sha]}))["sha"]

# 5) 更新分支引用
req("PATCH", f"{API}/repos/{repo}/git/refs/heads/{branch}",
    {"sha": new_commit, "force": False})
print("UPLOAD_OK " + remote)
PYEOF

log "已上传 $REMOTE 到 GitHub ($REPO)"

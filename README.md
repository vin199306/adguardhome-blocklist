# AdGuard Blocklist 自动同步

把网络上搜集到的 blocklist 源定时合并、去重，并自动推送 / 刷新到 AdGuard Home；
同时根据 AdGuard Home 的查询日志，持续累积「被拦截域名」清单（blockedlist.txt）。

## 目录结构

```
blocklists.txt              # 你维护的“blocklist 源链接清单”（每行一条，# 为注释）
scripts/build_blocklist.py  # 下载所有源 + 去重 -> blocklist.txt
scripts/agh_update.py        # 通知 AdGuard Home 更新规则
scripts/build_blockedlist.py # 解析 querylog.json -> blockedlist.txt（去重合并）
.github/workflows/schedule.yml # 每天定时执行
blocklist.txt               # 自动生成：所有源合并去重后的总规则（提交进仓库）
blockedlist.txt             # 自动生成：查询日志中累计的被拦截域名（提交进仓库）
```

## 工作流程（每天一次）

1. 读取 `blocklists.txt` 里的每个链接，下载内容。
2. 按行去重（忽略大小写、去掉注释与空行），合并写入 `blocklist.txt` 并提交。
3. 通过 AdGuard Home API 通知其更新规则：
   - `filter` 模式（默认）：确保 `AGH_FILTER_URL` 已作为订阅加入，并 `refresh` 刷新。
   - `rules` 模式：把 `blocklist.txt` 直接 `set_rules` 推送到「自定义过滤规则」（会覆盖原有自定义规则）。
4. 通过 SCP 从 AdGuard Home 服务器拉取 `querylog.json`。
5. 解析其中被拦截的域名，与已有 `blockedlist.txt` 去重合并后提交。

## 使用方法

### 1. 准备仓库
把本目录推送到 GitHub 私有（或公开）仓库。

### 2. 维护 `blocklists.txt`
往 `blocklists.txt` 里加你搜集到的 blocklist 链接，每行一条。
国内访问 GitHub 慢的源可用 `ghfast.top` 等代理前缀，例如你给的示例：
```
https://ghfast.top/https://github.com/zhuanshenlikaini/AdguardHome-Rules/releases/download/stable-latest/Black.txt
```

### 3. 配置 GitHub Secrets
在仓库 `Settings → Secrets and variables → Actions → Repository secrets` 添加：

| 名称 | 说明 | 必填 |
| --- | --- | --- |
| `AGH_BASE_URL` | AdGuard Home 地址，如 `http://home.example.com:3000` | 用于通知时必填 |
| `AGH_USER` | AdGuard Home 管理员用户名 | 用于通知时必填 |
| `AGH_PASSWORD` | AdGuard Home 管理员密码 | 用于通知时必填 |
| `AGH_UPDATE_MODE` | `filter`（默认）或 `rules` | 否 |
| `AGH_FILTER_URL` | `filter` 模式下 AGH 订阅的 blocklist 地址 | `filter` 模式必填 |
| `AGH_FILTER_NAME` | 订阅显示名称 | 否 |
| `AGH_BASE_PATH` | 反向代理下的基础路径，默认 `/control` | 否 |
| `AGH_VERIFY_SSL` | `true`/`false`，自签证书设 `false` | 否 |
| `AGH_SSH_HOST` | AdGuard Home 服务器 SSH 地址（用于拉 querylog） | 用于 blockedlist 时必填 |
| `AGH_SSH_PORT` | SSH 端口，默认 `22` | 否 |
| `AGH_SSH_USER` | SSH 用户名 | 用于 blockedlist 时必填 |
| `AGH_SSH_KEY` | SSH 私钥（内容） | 用于 blockedlist 时必填 |
| `AGH_QUERYLOG_PATH` | 服务器上 querylog.json 路径，默认 `/opt/AdGuardHome/data/querylog.json` | 否 |

未配置 `AGH_BASE_URL`：跳过通知步骤；未配置 `AGH_SSH_HOST`：跳过 blockedlist 步骤。两者互不影响。

### 4. 关于 `AGH_FILTER_URL`（filter 模式）
`blocklist.txt` 提交后可通过以下地址让 AdGuard Home 订阅（任选，国内推荐前两种）：
- `https://ghfast.top/https://raw.githubusercontent.com/OWNER/REPO/main/blocklist.txt`
- `https://cdn.jsdelivr.net/gh/OWNER/REPO@main/blocklist.txt`
- `https://raw.githubusercontent.com/OWNER/REPO/main/blocklist.txt`

把选中的地址填到 `AGH_FILTER_URL`。工作流每次更新 `blocklist.txt` 后调用 `refresh`，AdGuard Home 会重新拉取最新规则。

### 5. 触发
- 自动：每天 UTC 19:17（≈ 北京 03:17）。
- 手动：仓库 `Actions → AdGuard Blocklist Sync → Run workflow`。

## 隐私说明
- `querylog.json` 包含 DNS 查询记录，**不会**提交进仓库（已写入 `.gitignore`），仅在 runner 上临时处理。
- `blockedlist.txt` 仅含被拦截的域名，会提交进仓库，请按需选择公开/私有仓库。
- 提交信息带 `[skip ci]`，避免推送触发无限循环。

## 本地调试
```bash
# 生成合并规则
python scripts/build_blocklist.py
# 本地通知 AGH（先 export AGH_* 环境变量）
python scripts/agh_update.py
# 本地从 querylog 生成 blockedlist
python scripts/build_blockedlist.py --input querylog.json --output blockedlist.txt
```

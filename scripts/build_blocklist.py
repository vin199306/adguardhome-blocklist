#!/usr/bin/env python3
"""读取 blocklists.txt 中的源链接，逐一下载并按行去重，合并写入 blocklist.txt。

仅依赖 Python 标准库，无需 pip 安装。
"""
import os
import sys
import ssl
import urllib.request

BLOCKLISTS_FILE = os.environ.get("BLOCKLISTS_FILE", "blocklists.txt")
OUTPUT = os.environ.get("BLOCKLIST_OUTPUT", "blocklist.txt")
USER_AGENT = "Mozilla/5.0 (adguard-blocklist-sync)"
TIMEOUT = 60
RETRIES = 2


def load_sources(path):
    sources = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            sources.append(s)
    return sources


def download(url):
    # 支持本地文件路径（不含 http/https scheme 时按本地文件读取），方便放本地规则/调试
    if not url.startswith(("http://", "https://")):
        try:
            with open(os.path.expanduser(url), encoding="utf-8") as f:
                return f.read()
        except Exception as e:  # noqa: BLE001
            print(f"  ! 读取本地文件失败: {url} -> {e}", file=sys.stderr)
            return None
    last = None
    for attempt in range(RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"  ! 下载失败 (尝试 {attempt + 1}/{RETRIES + 1}): {url} -> {e}", file=sys.stderr)
    return None


def main():
    if not os.path.exists(BLOCKLISTS_FILE):
        print(f"缺少源文件: {BLOCKLISTS_FILE}", file=sys.stderr)
        sys.exit(1)

    sources = load_sources(BLOCKLISTS_FILE)
    print(f"共 {len(sources)} 个 blocklist 源")

    seen = set()
    rules = []
    counts = {}
    for url in sources:
        print(f"下载: {url}")
        text = download(url)
        if text is None:
            counts[url] = 0
            continue
        n = 0
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("!") or line.startswith("#"):
                continue
            key = line.lower()
            if key in seen:
                continue
            seen.add(key)
            rules.append(line)
            n += 1
        counts[url] = n
        print(f"  + {n} 条新规则")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(f"# 自动合并的 blocklist（由 adguard-blocklist-sync 生成），共 {len(rules)} 条\n")
        for r in rules:
            f.write(r + "\n")

    print(f"\n完成：写入 {OUTPUT}，合计 {len(rules)} 条规则")
    for url, c in counts.items():
        print(f"  {c:>6}  {url}")


if __name__ == "__main__":
    main()

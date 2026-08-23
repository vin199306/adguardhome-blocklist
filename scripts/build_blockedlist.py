#!/usr/bin/env python3
"""解析 AdGuard Home 的 querylog.json，提取被拦截的域名，与已有 blockedlist.txt 去重合并。

逻辑（对应需求）：
  - 解析 querylog.json 中所有条目，去重得到被拦截域名集合。
  - 将“现有 blockedlist.txt 中没有的”域名追加进去，写回 blockedlist.txt。

querylog.json 支持两种格式：
  - 每行一个 JSON 对象（AdGuard Home 默认落盘格式）
  - 单个 JSON 数组
被判定为“拦截”的依据：reason 以 "Filtered" 开头，或为 "BlockedService"。
"""
import os
import sys
import json
import argparse

BLOCKED_REASONS_PREFIX = ("Filtered",)
BLOCKED_REASONS_EXACT = {"BlockedService"}


def is_blocked(entry):
    reason = entry.get("reason") or ""
    if reason.startswith(BLOCKED_REASONS_PREFIX):
        return True
    if reason in BLOCKED_REASONS_EXACT:
        return True
    return False


def load_existing(path):
    out = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith("#"):
                    out.add(s.lower())
    return out


def parse_entries(text):
    text = text.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        return [data]
    except json.JSONDecodeError:
        entries = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="querylog.json")
    ap.add_argument("--output", default="blockedlist.txt")
    args = ap.parse_args()

    existing = load_existing(args.output)
    print(f"已有 blockedlist: {len(existing)} 条")

    if not os.path.exists(args.input):
        print(f"找不到 {args.input}，跳过（保留现有 blockedlist）", file=sys.stderr)
        if existing:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(f"# 由 AdGuard Home 查询日志中提取的已拦截域名，共 {len(existing)} 条\n")
                for d in sorted(existing):
                    f.write(d + "\n")
        sys.exit(0)

    with open(args.input, encoding="utf-8") as f:
        entries = parse_entries(f.read())

    new = set()
    total = 0
    blocked = 0
    for e in entries:
        total += 1
        if not is_blocked(e):
            continue
        blocked += 1
        q = e.get("question") or {}
        name = q.get("name") if isinstance(q, dict) else None
        if not name:
            continue
        name = name.rstrip(".").lower()
        if name:
            new.add(name)

    merged = existing | new
    added = new - existing
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(f"# 由 AdGuard Home 查询日志中提取的已拦截域名，共 {len(merged)} 条\n")
        for d in sorted(merged):
            f.write(d + "\n")

    print(f"解析条目 {total}，其中拦截 {blocked}")
    print(f"本次新增 {len(added)} 条，blockedlist 现共 {len(merged)} 条")


if __name__ == "__main__":
    main()

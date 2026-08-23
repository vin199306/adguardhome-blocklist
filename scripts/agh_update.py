#!/usr/bin/env python3
"""通知 AdGuard Home 更新规则。

两种模式（由 AGH_UPDATE_MODE 决定，默认 filter）：
  - filter: 确保 AGH_FILTER_URL 已作为订阅加入，并刷新全部过滤规则。
            适合大列表：把生成的 blocklist.txt 托管成可访问的 URL 让 AGH 订阅。
  - rules : 直接把 blocklist.txt 内容通过 set_rules 推送到“自定义过滤规则”。
            注意：这会【覆盖】AdGuard Home 里原有的全部自定义规则。

认证：优先使用 Basic Auth（用户名/密码），失败再尝试登录拿 session cookie。
"""
import os
import sys
import json
import base64
import ssl
import urllib.request
import urllib.error

BASE = os.environ.get("AGH_BASE_URL", "").rstrip("/")
BASE_PATH = os.environ.get("AGH_BASE_PATH", "/control").rstrip("/")
USER = os.environ.get("AGH_USER", "")
PASS = os.environ.get("AGH_PASSWORD", "")
MODE = os.environ.get("AGH_UPDATE_MODE", "filter").lower()
FILTER_URL = os.environ.get("AGH_FILTER_URL", "")
FILTER_NAME = os.environ.get("AGH_FILTER_NAME", "GitHub Blocklist Sync")
VERIFY_SSL = os.environ.get("AGH_VERIFY_SSL", "true").lower() != "false"


def ctx():
    if VERIFY_SSL:
        return ssl.create_default_context()
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


def req(method, path, body=None, headers=None, auth=True):
    url = BASE + BASE_PATH + path
    data = None
    hdrs = {"User-Agent": "adguard-blocklist-sync"}
    if headers:
        hdrs.update(headers)
    if body is not None:
        if isinstance(body, str):
            data = body.encode("utf-8")
        else:
            data = json.dumps(body).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
    if auth and USER:
        tok = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
        hdrs["Authorization"] = "Basic " + tok
    r = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30, context=ctx()) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def ensure_filter():
    if not FILTER_URL:
        print("filter 模式需要设置 AGH_FILTER_URL（AGH 订阅用的 blocklist 地址）", file=sys.stderr)
        return False

    status, body = req("GET", "/filtering/status")
    existing = []
    if status == 200:
        try:
            existing = json.loads(body).get("filters", [])
        except Exception:  # noqa: BLE001
            pass
    found = any((f.get("url") or "").rstrip("/") == FILTER_URL.rstrip("/") for f in existing)

    if not found:
        print(f"添加过滤订阅: {FILTER_URL}")
        s, b = req("POST", "/filtering/add_url",
                   {"name": FILTER_NAME, "url": FILTER_URL, "allowlist": False})
        if s != 200:
            print(f"  ! add_url 失败: {s} {b}", file=sys.stderr)
            return False
    else:
        print("过滤订阅已存在，跳过添加")

    print("刷新过滤规则...")
    s, b = req("POST", "/filtering/refresh", {"force": True})
    if s != 200:
        print(f"  ! refresh 失败: {s} {b}", file=sys.stderr)
        return False
    print("已通知 AdGuard Home 刷新规则")
    return True


def set_rules():
    out = os.environ.get("BLOCKLIST_OUTPUT", "blocklist.txt")
    if not os.path.exists(out):
        print(f"找不到 {out}", file=sys.stderr)
        return False
    with open(out, encoding="utf-8") as f:
        text = f.read()
    print(f"通过 set_rules 推送 {len(text.splitlines())} 行规则到自定义规则"
          f"（将覆盖原有自定义规则）")
    s, b = req("POST", "/filtering/set_rules", text,
               headers={"Content-Type": "text/plain"})
    if s != 200:
        print(f"  ! set_rules 失败: {s} {b}", file=sys.stderr)
        return False
    print("已更新 AdGuard Home 自定义过滤规则")
    return True


def main():
    if not BASE:
        print("未设置 AGH_BASE_URL，跳过 AdGuard Home 通知", file=sys.stderr)
        sys.exit(0)
    ok = ensure_filter() if MODE == "filter" else set_rules()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

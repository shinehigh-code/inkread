"""一键发布到 GitHub：建仓 → 推送 → 建 Release → 上传 exe。

用法（令牌只从环境变量读，绝不写进任何文件）：

    # PowerShell
    $env:GH_TOKEN = "ghp_xxx"; python tools/publish.py
    # bash
    GH_TOKEN=ghp_xxx python tools/publish.py

可选环境变量：
    REPO_NAME   仓库名，默认 inkread
    TAG         版本号，默认 v1.0.0
    ASSET       要上传的 exe，默认 dist/墨读.exe
    ASSET_NAME  附件名（必须是 ASCII，GitHub 会剥掉中文名），默认 inkread-windows-x64.exe
    DRY_RUN     设为 1 时只打印将要做的事，不实际请求
"""
from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.github.com"


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


TOKEN = env("GH_TOKEN") or env("GITHUB_TOKEN")
REPO = env("REPO_NAME", "inkread")
TAG = env("TAG", "v1.0.0")
ASSET = Path(env("ASSET", str(ROOT / "dist" / "墨读.exe")))
ASSET_NAME = env("ASSET_NAME", "inkread-windows-x64.exe")
DRY = env("DRY_RUN") == "1"

DESCRIPTION = "墨读 InkRead —— Windows 本地电子书与漫画阅读器（TXT/MD/EPUB/CBZ/CBR/CB7，离线、无网络请求）"
RELEASE_BODY = """## 墨读 InkRead v1.0.0

Windows 下的本地电子书与漫画阅读器，单文件绿色版，双击即用。

**格式**：TXT / Markdown / EPUB / CBZ / CBR / CB7 / CBT / 图片文件夹

**阅读**：翻页与滚动两种模式、鼠标滚轮翻页、五套主题、字体字号行距页宽可调、目录、书签、全文搜索、
离线 KaTeX 公式渲染、繁简五档转换、系统语音逐句朗读并跟随高亮（可调语速/音调/音量）

**漫画**：单页/双页、适应高度/宽度/原始大小/连续滚动、左到右与右到左

**窗口**：无边框自绘界面，标题栏可拖动、边缘可缩放、双击标题栏最大化

**隐私**：全部本地处理，界面走本机回环端口，程序不发起任何网络请求，不收集任何信息。
EPUB/Markdown 内嵌 HTML 走白名单净化，压缩包读取有路径越界防护。

**系统要求**：Windows 10/11（需要 WebView2 运行时，系统一般已自带）。
`.cbr` 需要系统安装 WinRAR 或 unar。

源码、构建方式与第三方许可见仓库 README 与 THIRD-PARTY-NOTICES.md。
"""


def call(method: str, url: str, data=None, ctype: str = "application/json", raw: bytes | None = None,
         extra_headers: dict | None = None):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "inkread-publish",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = None
    if raw is not None:
        body = raw
        headers["Content-Type"] = ctype
    elif data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            text = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(text) if text.strip().startswith(("{", "[")) else text)
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        return e.code, text


def step(msg: str):
    print(f"\n=== {msg} ===", flush=True)


def main() -> int:
    if not TOKEN:
        print("缺少 GH_TOKEN 环境变量（classic PAT，勾选 repo 即可）")
        return 2
    if not ASSET.exists():
        print(f"找不到要上传的文件：{ASSET}（先运行 python build.py）")
        return 2
    size_mb = ASSET.stat().st_size / 1048576
    print(f"仓库 {REPO}，版本 {TAG}，附件 {ASSET.name}（{size_mb:.1f} MB）→ 上传名 {ASSET_NAME}")
    if DRY:
        print("DRY_RUN=1，只演示不执行")
        return 0

    step("确认账号")
    st, me = call("GET", f"{API}/user")
    if st != 200:
        print("令牌无效或权限不足：", st, str(me)[:200])
        return 1
    owner = me["login"]
    print("账号:", owner)

    step("创建仓库（已存在则跳过）")
    st, info = call("GET", f"{API}/repos/{owner}/{REPO}")
    if st == 200:
        print(f"已存在：{info['html_url']}")
        html_url = info["html_url"]
    else:
        st, info = call("POST", f"{API}/user/repos", {
            "name": REPO,
            "description": DESCRIPTION,
            "homepage": "",
            "private": False,
            "has_issues": True,
            "has_wiki": False,
            "auto_init": False,
        })
        if st not in (200, 201):
            print("建仓失败：", st, str(info)[:300])
            return 1
        html_url = info["html_url"]
        print("已创建：", html_url)

    step("推送代码")
    remote = f"https://{owner}:{TOKEN}@github.com/{owner}/{REPO}.git"
    if subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT,
                      capture_output=True).returncode != 0:
        subprocess.run(["git", "remote", "add", "origin", f"https://github.com/{owner}/{REPO}.git"], cwd=ROOT)
    # 用一次性 URL 推送，避免令牌落进 .git/config
    r = subprocess.run(["git", "push", remote, "main:main", "-f", "--quiet"], cwd=ROOT)
    if r.returncode != 0:
        print("推送失败，请检查令牌 scope 是否含 repo")
        return 1
    print("推送完成")

    step("创建 Release")
    st, rel = call("GET", f"{API}/repos/{owner}/{REPO}/releases/tags/{TAG}")
    if st == 200:
        print("Release 已存在，复用：", rel["html_url"])
    else:
        st, rel = call("POST", f"{API}/repos/{owner}/{REPO}/releases", {
            "tag_name": TAG,
            "name": f"墨读 InkRead {TAG}",
            "body": RELEASE_BODY,
            "draft": False,
            "prerelease": False,
        })
        if st not in (200, 201):
            print("创建 Release 失败：", st, str(rel)[:300])
            return 1
        print("已创建：", rel["html_url"])

    step("上传附件")
    # 先删同名旧附件，便于重复发布
    st, assets = call("GET", f"{API}/repos/{owner}/{REPO}/releases/{rel['id']}/assets")
    if st == 200:
        for a in assets:
            if a["name"] == ASSET_NAME:
                call("DELETE", f"{API}/repos/{owner}/{REPO}/releases/assets/{a['id']}")
                print("已删除同名旧附件")

    upload = rel["upload_url"].split("{")[0]
    ctype = mimetypes.guess_type(ASSET_NAME)[0] or "application/octet-stream"
    st, res = call("POST", f"{upload}?name={urllib.parse.quote(ASSET_NAME)}",
                   raw=ASSET.read_bytes(), ctype="application/octet-stream",
                   extra_headers={"Content-Type": "application/octet-stream"})
    if st not in (200, 201):
        print("上传失败：", st, str(res)[:300])
        return 1
    print("附件地址：", res["browser_download_url"])

    print("\n发布完成：")
    print("  仓库：", html_url)
    print("  版本：", rel["html_url"])
    print("  下载：", res["browser_download_url"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

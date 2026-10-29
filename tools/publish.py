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
TAG = env("TAG", "v1.1.0")
ASSET = Path(env("ASSET", str(ROOT / "dist" / "墨读.exe")))
ASSET_NAME = env("ASSET_NAME", "inkread-windows-x64.exe")
DRY = env("DRY_RUN") == "1"

DESCRIPTION = (
    "Windows 本地电子书与漫画阅读器：TXT / Markdown / EPUB / CBZ / CBR / CB7，"
    "支持语音朗读、繁简转换、离线公式渲染、隐私阅读与选中翻译。单文件绿色版，全部本地处理。"
)

UPDATE_NOTES = f"""本次更新（{TAG}）修掉两个用起来别扭的地方，另外加了隐私阅读和选中操作，顺手把体积砍了一半。

**修好的**

- 底部进度条现在只管当前这一章：翻页模式跳页、滚动模式跳位置，左右两侧新加了「上一章 / 下一章」按钮。只有一章的书不会再一拖就回到开头
- 右侧那条细滚动条之前被翻页热区盖住、完全拖不动，现在可以直接拖着快速下滑；正文也不再被透明按钮挡住，能正常框选文字

**新加的**

- **隐私阅读**：从侧栏进入，用这个模式打开的书不进书架、不记进度、不留书签；隐私 EPUB 的临时解析文件在关闭阅读或退出程序时清掉
- **选中文字操作**：正文里选中一段，可以直接朗读、复制，或者做离线中英互译

**排版**

- 新增字重调节，默认排版改成 18px / 字重 400 / 行距 1.85 / 页宽 780px
- 中文两端对齐、正文留白、窄窗口下的底部栏布局都调了一遍
- 旧版本没改过排版的，升级会自动迁移到新默认值；自己调过的保持不变

**体积和启动**

- 数学公式改成遇到公式才加载，封面不再转码、交给浏览器直接解码，打包时剔除了用不到的运行库
- 安装包从 40.4 MiB 降到 23.7 MiB，小了约 41%

关于「中英互译」的说明：它走的是内置基础词库，完全离线，不会把选中的文字发出去。
能翻的只是常见词和简单句，专有名词和复杂长句会保留原文并给出提示，别把它当在线翻译用。

---

"""

INTRO = """## 这个程序是做什么的

Windows 上的本地阅读器，电子书和漫画都能看。文件只从本机读取，不联网，不需要账号。

| 类型 | 格式 |
| --- | --- |
| 电子书 | TXT、Markdown、EPUB |
| 漫画 | CBZ、ZIP、CBR、RAR、CB7、7Z、CBT、TAR；也可以直接选一个装满图片的文件夹 |

## 主要功能

**看小说**
TXT 自动判断编码（UTF-8、GBK、Big5、UTF-16），按「第 N 章」「序章」「番外」这类标题自动分章。
翻页和滚动两种模式随时切换，鼠标滚轮可以翻页，读到哪里自己记住。

**看笔记和电子书**
Markdown 的标题、表格、代码块、图片按原文排版，数学公式用内置的 KaTeX 离线渲染。
EPUB 支持目录、封面、插图，书里的内链可以点。

**看漫画**
单页或双页并排，适应高度 / 适应宽度 / 原始尺寸，长条漫可以连续滚动；页序支持从左到右和从右到左。

**听书与选词**
用 Windows 自带的语音逐句朗读，读到哪一句哪一句高亮，翻页模式自动翻页、滚动模式自动滚动，
一章读完接着读下一章。可以暂停、跳句，语速音调音量都能调。
选中正文后还能直接朗读、复制，或者用内置基础词库做离线中英互译——未收录的专名和复杂句式会保留原文，不会上传文字。

**其它**
- 五套主题：纸、墨、茶、苔、夜
- 字体、字号、字重、行距、页宽、段距可调
- 目录、书签、单本书内全文搜索
- 繁简五档：原文 / 简体 / 繁體 / 繁體（台）/ 繁體（港）
- 书库支持搜索和排序；TXT、Markdown 没有封面时会自动生成一张排版封面
- 隐私阅读：用这个模式打开的书不进书架、不记进度、不留书签

## 关于隐私

程序只读本机文件，不发起任何外网请求，界面的服务只监听 `127.0.0.1` 的临时端口。
EPUB / Markdown 里的 HTML 走白名单净化，压缩包读取有路径越界防护。

## 系统要求

Windows 10 / 11，需要 WebView2 运行时（系统一般已自带）。
`.cbr` 需要系统装有 WinRAR 或 unar。

源码、构建方法与第三方组件许可，见仓库的 README 与 THIRD-PARTY-NOTICES.md。
"""

RELEASE_BODY = UPDATE_NOTES + INTRO

# 旧版本说明默认不动（需要改写时再传 OLD_TAG=vX.Y.Z 和 OLD_BODY 环境变量）
OLD_TAG = env("OLD_TAG", "")
OLD_BODY = """首个版本。

Windows 上的本地阅读器，电子书和漫画都能看。文件只从本机读取，不联网，不需要账号。

支持 TXT、Markdown、EPUB 三种电子书，CBZ / ZIP / CBR / RAR / CB7 / 7Z / CBT / TAR 等漫画格式，
也可以直接把装满图片的文件夹当漫画导入。

功能包括：翻页与滚动两种阅读模式、五套主题、字号行距页宽可调、目录、书签、单本书内全文搜索、
繁简五档转换、离线公式渲染、用系统语音逐句朗读并跟随高亮、漫画单页双页与四种缩放。

详细说明见仓库 README。

这个版本有两个已知问题，已在 v1.0.1 修复，建议直接使用新版：
- 用「打开方式」打开电子书时，窗口只停在书库首页
- 拖动底部进度条会连带动窗口
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

    step("更新仓库简介")
    st, _ = call("PATCH", f"{API}/repos/{owner}/{REPO}", {"description": DESCRIPTION})
    print("已更新" if st == 200 else f"更新失败：{st}")

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

    # 把上一个版本的说明文字也换成新版（原来那版写得太营销，而且没交代已知问题）
    if OLD_TAG and OLD_TAG != TAG:
        step(f"更新旧版本说明（{OLD_TAG}）")
        st, old = call("GET", f"{API}/repos/{owner}/{REPO}/releases/tags/{OLD_TAG}")
        if st == 200:
            st2, _ = call("PATCH", f"{API}/repos/{owner}/{REPO}/releases/{old['id']}", {"body": OLD_BODY})
            print(f"说明已更新：{old['html_url']}" if st2 == 200 else f"更新失败：{st2}")
        else:
            print(f"没有 {OLD_TAG} 这个版本，跳过")

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

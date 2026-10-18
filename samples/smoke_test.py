"""后端冒烟测试：起本地服务，逐个格式走通 API。"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 每次跑都从干净的数据目录开始，避免上一轮测试加进去的书影响数量断言
_TESTDATA = ROOT / ".testdata"
if _TESTDATA.exists():
    import shutil

    shutil.rmtree(_TESTDATA, ignore_errors=True)

os.environ["INKREAD_HOME"] = str(_TESTDATA)

from app.server import serve  # noqa: E402

httpd, port = serve()
BASE = f"http://127.0.0.1:{port}"
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

passed, failed = [], []


def check(name: str, cond: bool, detail: str = ""):
    (passed if cond else failed).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  | {detail}" if detail and not cond else ""))


def get(path: str):
    import urllib.error

    try:
        with _opener.open(BASE + path, timeout=10) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type", "")


def post(path: str, body: dict):
    import urllib.error

    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with _opener.open(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"error": raw[:200]}


# 1. 设置
st, settings = get("/api/settings")[0], json.loads(get("/api/settings")[1])
check("GET /api/settings", st == 200 and settings["theme"] == "paper")

# 2. 添加样本
samples = ROOT / "samples"
paths = [
    str(samples / "novel_gbk.txt"),
    str(samples / "traditional_big5.txt"),
    str(samples / "notes.md"),
    str(samples / "demo.epub"),
    str(samples / "comic.cbz"),
    str(samples / "comic.7z"),
    str(samples / "comic_folder"),
]
st, res = post("/api/library/add", {"paths": paths})
check("POST /api/library/add", st == 200 and len(res["added"]) == 7 and not res["errors"], str(res.get("errors")))

books = json.loads(get("/api/library")[1])["books"]
by_kind = {}
for b in books:
    by_kind.setdefault(b["kind"], []).append(b)
check("书库含 7 本书", len(books) == 7, str([b["title"] for b in books]))

# 3. GBK 小说
novel = next((b for b in by_kind.get("txt", []) if b["fmt"] == "txt" and b["title"] == "雾港往事"), None)
if novel:
    ch = json.loads(get(f"/api/book/{novel['id']}/chapter/1")[1])
    check("GBK 小说解码+章节", "老周" in ch["html"] and ch["title"] == "第1章 雾中的航标", ch["title"])
    check("章节标题不重复出现", not ch["html"].startswith(f"<p>{ch['title']}</p>"), ch["html"][:60])
    hits = json.loads(get(f"/api/book/{novel['id']}/search?q=" + quote("航标灯"))[1])["results"]
    check("全文搜索", len(hits) >= 1)

# 4. Big5 繁体 + 繁简转换
trad = next((b for b in by_kind.get("txt", []) if b["title"] == "霧港往事"), None)
if trad:
    ch0 = json.loads(get(f"/api/book/{trad['id']}/chapter/1")[1])
    post("/api/settings", {"convert": "t2s"})
    ch1 = json.loads(get(f"/api/book/{trad['id']}/chapter/1")[1])
    check("Big5 解码", "碼頭" in ch0["html"])
    check("繁→简转换", "码头" in ch1["html"] and "霧" not in ch1["html"], ch1["html"][:80])
    post("/api/settings", {"convert": "none"})

# 5. Markdown + 数学
md = next((b for b in by_kind.get("md", [])), None)
if md:
    ch = json.loads(get(f"/api/book/{md['id']}/chapter/0")[1])
    check("md 渲染表格/公式", "<table>" in ch["html"] and "E_{tx}" in ch["html"] and "katex" not in ch["html"])
    check("md 目录锚点", len(ch.get("anchors", [])) >= 3)

# 6. EPUB
epub = next((b for b in by_kind.get("epub", [])), None)
if epub:
    info = json.loads(get(f"/api/book/{epub['id']}")[1])
    check("epub 目录", [t["title"] for t in info["toc"]][:1] == ["第一章 铁锈味的雾"])
    ch = json.loads(get(f"/api/book/{epub['id']}/chapter/0")[1])
    check("epub 净化脚本", "<script>" not in ch["html"] and "alert" not in ch["html"])
    check("epub 图片重写", f"/api/book/{epub['id']}/asset/cover.png" in ch["html"])
    check("epub 外链图片置空", 'src="http' not in ch["html"])
    check("epub 内链转 data-goto", "data-goto" in ch["html"])
    st, data, ctype = get(f"/api/book/{epub['id']}/cover")
    check("epub 封面", st == 200 and ctype == "image/png" and len(data) > 1000)
    st, data, ctype = get(f"/api/book/{epub['id']}/asset/cover.png")
    check("epub 资源服务", st == 200 and len(data) > 1000)

# 7. 漫画 cbz / 7z / 文件夹
for b in by_kind.get("comic", []):
    st, data, ctype = get(f"/api/book/{b['id']}/page/0")
    check(f"漫画取页 {b['fmt']}", st == 200 and ctype == "image/png" and len(data) > 5000)
    info = json.loads(get(f"/api/book/{b['id']}")[1])
    check(f"漫画页数 {b['fmt']}", info["meta"]["pages"] == 8, str(info["meta"].get("pages")))
    st, data, ctype = get(f"/api/book/{b['id']}/cover")
    check(f"漫画封面 {b['fmt']}", st == 200)

# 8. 进度与书签
if novel:
    st, r = post(f"/api/book/{novel['id']}/progress", {"chapter": 2, "page": 3, "pct": 0.42})
    check("保存进度", st == 200 and r["progress"]["chapter"] == 2)
    st, r = post(f"/api/book/{novel['id']}/bookmarks", {"chapter": 2, "label": "测试书签", "excerpt": "雾从江面漫上来"})
    check("添加书签", st == 200 and len(r["bookmarks"]) == 1)
    st, r = post(f"/api/book/{novel['id']}/bookmarks/delete", {"id": r["bookmarks"][0]["id"]})
    check("删除书签", len(r["bookmarks"]) == 0)

# 9. 安全：静态路径穿越
st, _, _ = get("/assets/../app/config.py")
check("静态路径穿越被拒", st == 403, str(st))

# 10. 运行中打开文件（「用墨读打开」第二个文件时走这条）
st, raw, _ = get("/api/ping")
r = json.loads(raw)
check("实例存活探测", st == 200 and r.get("ok") is True, str(r)[:80])

new_book = ROOT / "samples" / "cli_open.md"
new_book.write_text("# 命令行打开测试\n\n这一章用来验证从外部打开文件。\n", "utf-8")
st, r = post("/api/open-file", {"paths": [str(new_book)]})
check("运行中打开文件", st == 200 and r.get("id") and r["added"][0]["title"] == "命令行打开测试", str(r)[:120])
check("返回跳转用的书籍 id", st == 200 and len(str(r.get("id"))) == 12, str(r.get("id")))

st, r = post("/api/open-file", {"paths": []})
check("空路径被拒", st == 400, str(st))

st, r = post("/api/open-file", {"paths": [str(ROOT / "samples" / "不存在.epub")]})
check("无效路径被拒", st == 400 and "不存在" in str(r), str(r)[:80])
try:
    new_book.unlink()
except OSError:
    pass

print(f"\n===== {len(passed)} 通过, {len(failed)} 失败 =====")
if failed:
    print("失败项：", failed)
httpd.shutdown()
sys.exit(1 if failed else 0)

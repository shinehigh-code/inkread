"""本地 HTTP 服务：静态资源 + JSON API + 书籍内容。

仅监听 127.0.0.1，不发起任何外网请求。
"""
from __future__ import annotations

import json
import os
import re
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import config
from .handlers import BookError
from .library import Library
from .textproc import safe_join

DEBUG = bool(os.environ.get("INKREAD_DEBUG"))

DEFAULT_SETTINGS = {
    "theme": "paper",
    "font": "song",
    "size": 19,
    "lineHeight": 1.9,
    "width": 760,
    "para": 0.9,
    "mode": "page",
    "convert": "none",
    "comic": {"fit": "fit-height", "spread": "single", "dir": "ltr"},
    "tts": {"voice": "", "rate": 1.0, "pitch": 1.0, "volume": 1.0},
}


class Ctx:
    def __init__(self):
        self.lib = Library()
        self.settings = json.loads(json.dumps(DEFAULT_SETTINGS))
        # 由 main 注入：运行中收到新文件时，通知前端跳到对应书籍
        self.navigate = None
        self._load_settings()

    def _load_settings(self):
        f = config.data_dir() / "settings.json"
        if f.exists():
            try:
                data = json.loads(f.read_text("utf-8"))
                for k, v in data.items():
                    if isinstance(v, dict) and isinstance(self.settings.get(k), dict):
                        self.settings[k].update(v)
                    else:
                        self.settings[k] = v
            except Exception:
                pass

    def save_settings(self):
        f = config.data_dir() / "settings.json"
        f.write_text(json.dumps(self.settings, ensure_ascii=False, indent=1), "utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "InkRead/" + config.VERSION
    protocol_version = "HTTP/1.1"

    @property
    def ctx(self) -> Ctx:
        return self.server.ctx  # type: ignore[attr-defined]

    # ---------------- 基础设施
    def log_message(self, fmt, *args):
        if DEBUG:
            try:
                with open(config.data_dir() / "server.log", "a", encoding="utf-8") as f:
                    f.write("%s - %s\n" % (self.address_string(), fmt % args))
            except Exception:
                pass

    def _read_body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return {}
        if n <= 0 or n > 8 * 1024 * 1024:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def _json(self, obj, code: int = 200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _bytes(self, data: bytes, ctype: str, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=3600")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ---------------- 路由
    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def _dispatch(self, method: str):
        try:
            u = urlparse(self.path)
            path = u.path
            if len(path) > 1 and path.endswith("/"):
                path = path.rstrip("/")
            qs = parse_qs(u.query)
            body = self._read_body() if method == "POST" else {}
            fn = self._match(method, path)
            if fn is None:
                return self._json({"error": "接口不存在"}, 404)
            result = fn(qs, body, path)
            if isinstance(result, tuple):
                return self._bytes(result[0], result[1], result[2] if len(result) > 2 else 200)
            self._json(result)
        except BookError as e:
            self._json({"error": str(e)}, 400)
        except Exception as e:
            if DEBUG:
                traceback.print_exc()
            self._json({"error": f"服务器内部错误：{e}"}, 500)

    def _match(self, method: str, path: str):
        ctx = self.ctx

        # ---- 静态资源
        if method == "GET" and (path == "/" or path.startswith("/assets/") or path == "/favicon.ico"):
            def serve_static(qs, body, p):
                rel = "index.html" if p in ("/",) else p.lstrip("/")
                if rel == "favicon.ico":
                    rel = "assets/favicon.svg"
                root = config.web_dir().resolve()
                target = safe_join(str(root), rel)
                if not target:
                    return b"forbidden", "text/plain", 403
                f = Path(target)
                if not f.is_file():
                    return b"not found", "text/plain", 404
                ctype = {
                    ".html": "text/html; charset=utf-8",
                    ".css": "text/css; charset=utf-8",
                    ".js": "text/javascript; charset=utf-8",
                    ".svg": "image/svg+xml",
                    ".woff2": "font/woff2", ".woff": "font/woff",
                    ".ttf": "font/ttf", ".png": "image/png",
                    ".json": "application/json", ".map": "application/json",
                }.get(f.suffix.lower(), "application/octet-stream")
                return f.read_bytes(), ctype

            return serve_static

        # ---- 实例存活探测（「用墨读打开」第二个文件时用来找已运行的窗口）
        if path == "/api/ping" and method == "GET":
            return lambda qs, body, p: {"ok": True, "app": config.APP_NAME, "version": config.VERSION}

        # ---- 运行中打开文件：入库并让前端跳过去
        if path == "/api/open-file" and method == "POST":
            def open_file(qs, body, p):
                paths = body.get("paths") or []
                if not isinstance(paths, list) or not paths:
                    raise BookError("没有要打开的文件")
                res = ctx.lib.add([str(x) for x in paths][:200])
                if not res["added"]:
                    msg = res["errors"][0].get("error") if res["errors"] else "无法打开该文件"
                    raise BookError(msg)
                bid = res["added"][0]["id"]
                if callable(ctx.navigate):
                    try:
                        ctx.navigate(bid)
                    except Exception:
                        pass
                return {"ok": True, "id": bid, "added": res["added"], "errors": res["errors"]}

            return open_file

        # ---- 设置
        if path == "/api/settings":
            if method == "GET":
                return lambda qs, body, p: ctx.settings
            if method == "POST":
                def save_settings(qs, body, p):
                    for k, v in body.items():
                        if isinstance(v, dict) and isinstance(ctx.settings.get(k), dict):
                            ctx.settings[k].update(v)
                        else:
                            ctx.settings[k] = v
                    ctx.save_settings()
                    return ctx.settings

                return save_settings

        # ---- 书库
        if path in ("/api/library", "/api/library/add"):
            if method == "GET":
                def library(qs, body, p):
                    sort = (qs.get("sort") or ["recent"])[0]
                    q = (qs.get("q") or [""])[0]
                    return {"books": ctx.lib.list(sort, q)}

                return library
            if method == "POST":
                def add(qs, body, p):
                    paths = body.get("paths") or []
                    if not isinstance(paths, list) or not paths:
                        raise BookError("没有要添加的文件")
                    return ctx.lib.add([str(x) for x in paths][:200])

                return add

        if path == "/api/library/remove" and method == "POST":
            def remove(qs, body, p):
                ok = ctx.lib.remove(str(body.get("id") or ""))
                return {"ok": ok}

            return remove

        # ---- 书籍
        m = re.fullmatch(r"/api/book/([0-9a-f]{12})", path)
        if m and method == "GET":
            bid = m.group(1)

            def book_info(qs, body, p):
                meta = ctx.lib.get(bid)
                if not meta:
                    raise BookError("书籍不在书库中")
                handle = ctx.lib.registry.get(meta)
                try:
                    toc = handle.toc()
                except Exception:
                    toc = []
                return {
                    "meta": meta,
                    "toc": toc,
                    "progress": meta.get("progress"),
                    "bookmarks": meta.get("bookmarks", []),
                }

            return book_info

        m = re.fullmatch(r"/api/book/([0-9a-f]{12})/chapter/(\d+)", path)
        if m and method == "GET":
            bid, idx = m.group(1), int(m.group(2))

            def chapter(qs, body, p):
                meta = ctx.lib.get(bid)
                if not meta:
                    raise BookError("书籍不在书库中")
                mode = (qs.get("mode") or [ctx.settings["convert"]])[0]
                handle = ctx.lib.registry.get(meta)
                return handle.chapter(idx, mode)

            return chapter

        m = re.fullmatch(r"/api/book/([0-9a-f]{12})/page/(\d+)", path)
        if m and method == "GET":
            bid, idx = m.group(1), int(m.group(2))

            def page(qs, body, p):
                meta = ctx.lib.get(bid)
                if not meta:
                    raise BookError("书籍不在书库中")
                if meta["kind"] != "comic":
                    raise BookError("该书籍不是漫画")
                handle = ctx.lib.registry.get(meta)
                data, ctype = handle.page(idx)
                return data, ctype

            return page

        m = re.fullmatch(r"/api/book/([0-9a-f]{12})/cover", path)
        if m and method == "GET":
            bid = m.group(1)

            def cover(qs, body, p):
                f = config.data_dir() / "cache" / "covers" / f"{bid}.png"
                if not f.is_file():
                    return b"", "image/png", 404
                return f.read_bytes(), "image/png"

            return cover

        m = re.fullmatch(r"/api/book/([0-9a-f]{12})/asset/(.+)", path)
        if m and method == "GET":
            bid, rel = m.group(1), unquote(m.group(2))

            def asset(qs, body, p):
                meta = ctx.lib.get(bid)
                if not meta or meta["kind"] != "epub":
                    raise BookError("资源不存在")
                cache = config.data_dir() / "cache" / f"epub_{bid}"
                target = safe_join(str(cache), rel)
                if not target:
                    raise BookError("非法路径")
                f = Path(target)
                if not f.is_file():
                    raise BookError("资源不存在")
                ctype = {
                    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
                    ".bmp": "image/bmp", ".css": "text/css", ".ttf": "font/ttf",
                    ".woff": "font/woff", ".woff2": "font/woff2", ".otf": "font/otf",
                }.get(f.suffix.lower(), "application/octet-stream")
                return f.read_bytes(), ctype

            return asset

        m = re.fullmatch(r"/api/book/([0-9a-f]{12})/progress", path)
        if m and method == "POST":
            bid = m.group(1)

            def progress(qs, body, p):
                r = ctx.lib.set_progress(bid, body)
                if r is None:
                    raise BookError("书籍不在书库中")
                return {"ok": True, "progress": r}

            return progress

        m = re.fullmatch(r"/api/book/([0-9a-f]{12})/bookmarks", path)
        if m:
            bid = m.group(1)
            if method == "GET":
                def bm_list(qs, body, p):
                    meta = ctx.lib.get(bid)
                    return {"bookmarks": (meta or {}).get("bookmarks", [])}

                return bm_list
            if method == "POST":
                def bm_add(qs, body, p):
                    ctx.lib.touch(bid)
                    return {"bookmarks": ctx.lib.add_bookmark(bid, body)}

                return bm_add

        m = re.fullmatch(r"/api/book/([0-9a-f]{12})/bookmarks/delete", path)
        if m and method == "POST":
            bid = m.group(1)

            def bm_del(qs, body, p):
                return {"bookmarks": ctx.lib.remove_bookmark(bid, str(body.get("id") or ""))}

            return bm_del

        m = re.fullmatch(r"/api/book/([0-9a-f]{12})/search", path)
        if m and method == "GET":
            bid = m.group(1)

            def search(qs, body, p):
                meta = ctx.lib.get(bid)
                if not meta:
                    raise BookError("书籍不在书库中")
                kw = (qs.get("q") or [""])[0].strip()
                if len(kw) < 1:
                    return {"results": []}
                mode = (qs.get("mode") or [ctx.settings["convert"]])[0]
                handle = ctx.lib.registry.get(meta)
                if not hasattr(handle, "search"):
                    return {"results": []}
                return {"results": handle.search(kw, mode)}

            return search

        return None


def serve(host: str = "127.0.0.1", port: int = 0) -> tuple[ThreadingHTTPServer, int]:
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    httpd.ctx = Ctx()  # type: ignore[attr-defined]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, httpd.server_address[1]

"""书库：元数据、阅读进度、书签、封面缓存。"""
from __future__ import annotations

import hashlib
import io
import json
import time
from pathlib import Path

from PIL import Image

from .config import classify, data_dir
from .handlers import BookError, Registry


def book_id(path: str) -> str:
    return hashlib.sha1(str(Path(path).resolve()).encode("utf-8")).hexdigest()[:12]


def _fresh_progress() -> dict:
    return {"chapter": 0, "page": 0, "scroll": 0.0, "pct": 0.0, "ts": 0.0}


class Library:
    def __init__(self):
        self.file = data_dir() / "library.json"
        self.data = self._load()
        self.registry = Registry(cap=10)

    # ---------------- 持久化
    def _load(self) -> dict:
        if self.file.exists():
            try:
                d = json.loads(self.file.read_text("utf-8"))
                if isinstance(d, dict) and isinstance(d.get("books"), dict):
                    return d
            except Exception:
                pass
        return {"books": {}, "order": []}

    def save(self):
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), "utf-8")
        tmp.replace(self.file)

    # ---------------- 增删
    def add(self, paths: list[str]) -> dict:
        added, errors = [], []
        for p in paths:
            try:
                meta = self._scan(p)
                bid = meta["id"]
                old = self.data["books"].get(bid)
                if old:
                    old.update({k: v for k, v in meta.items() if k not in ("progress", "bookmarks")})
                    meta = old
                else:
                    self.data["books"][bid] = meta
                    self.data["order"].insert(0, bid)
                added.append(meta)
            except BookError as e:
                errors.append({"path": p, "error": str(e)})
            except Exception as e:
                errors.append({"path": p, "error": f"无法读取：{e}"})
        if added:
            self.save()
        return {"added": added, "errors": errors}

    def _scan(self, path: str) -> dict:
        p = Path(path)
        kind = classify(str(p))
        if kind is None:
            raise BookError("不支持的文件类型")
        if not p.exists():
            raise BookError("文件不存在")
        meta = {
            "id": book_id(str(p)),
            "path": str(p.resolve()),
            "kind": kind,
            "fmt": p.suffix.lower().lstrip(".") if p.is_file() else "dir",
            "title": p.stem,
            "author": "",
            "size": p.stat().st_size if p.is_file() else 0,
            "added_at": time.time(),
            "last_read": 0.0,
            "progress": _fresh_progress(),
            "bookmarks": [],
            "has_cover": False,
        }
        handle = self.registry.get(meta)
        try:
            info = handle.meta()
            meta["title"] = (info.get("title") or "").strip() or meta["title"]
            meta["author"] = (info.get("author") or "").strip()
            if kind == "comic":
                meta["pages"] = handle.page_count()
            elif kind in ("txt", "md", "epub"):
                meta["chapters"] = len(handle.toc())
            self._make_cover(meta, handle)
        finally:
            self.registry.drop(meta["id"])  # 扫描只是预览，句柄交还
        return meta

    def _make_cover(self, meta: dict, handle):
        data = None
        try:
            if meta["kind"] == "comic":
                data, _ctype = handle.page(0)
            elif meta["kind"] == "epub":
                got = handle.cover_bytes()
                if got:
                    data, _ctype = got
            if not data:
                return
            img = Image.open(io.BytesIO(data))
            img = img.convert("RGB")
            img.thumbnail((360, 520))
            out = data_dir() / "cache" / "covers" / f"{meta['id']}.png"
            img.save(out, "PNG", optimize=True)
            meta["has_cover"] = True
        except Exception:
            meta["has_cover"] = False

    def remove(self, bid: str) -> bool:
        if bid not in self.data["books"]:
            return False
        self.registry.drop(bid)
        cover = data_dir() / "cache" / "covers" / f"{bid}.png"
        if cover.exists():
            try:
                cover.unlink()
            except Exception:
                pass
        del self.data["books"][bid]
        if bid in self.data["order"]:
            self.data["order"].remove(bid)
        self.save()
        return True

    # ---------------- 查询
    def list(self, sort: str = "recent", q: str = "") -> list[dict]:
        books = list(self.data["books"].values())
        if q:
            ql = q.lower()
            books = [b for b in books if ql in b["title"].lower() or ql in b["path"].lower()]
        if sort == "title":
            books.sort(key=lambda b: b["title"].lower())
        elif sort == "added":
            books.sort(key=lambda b: b.get("added_at", 0), reverse=True)
        else:
            books.sort(key=lambda b: b.get("last_read", 0) or b.get("added_at", 0), reverse=True)
        return books

    def get(self, bid: str) -> dict | None:
        return self.data["books"].get(bid)

    # ---------------- 进度 / 书签
    def touch(self, bid: str):
        b = self.data["books"].get(bid)
        if b:
            b["last_read"] = time.time()

    def set_progress(self, bid: str, progress: dict):
        b = self.data["books"].get(bid)
        if not b:
            return None
        b["progress"] = {
            "chapter": int(progress.get("chapter", 0)),
            "page": int(progress.get("page", 0)),
            "scroll": float(progress.get("scroll", 0.0)),
            "pct": float(progress.get("pct", 0.0)),
            "ts": time.time(),
        }
        b["last_read"] = time.time()
        self.save()
        return b["progress"]

    def add_bookmark(self, bid: str, bm: dict) -> list:
        b = self.data["books"].get(bid)
        if not b:
            return []
        item = {
            "id": hashlib.sha1(f"{bid}{time.time()}".encode()).hexdigest()[:8],
            "chapter": int(bm.get("chapter", 0)),
            "loc": bm.get("loc", ""),
            "label": (bm.get("label") or "")[:40],
            "excerpt": (bm.get("excerpt") or "")[:120],
            "created": time.time(),
        }
        b.setdefault("bookmarks", []).insert(0, item)
        self.save()
        return b["bookmarks"]

    def remove_bookmark(self, bid: str, bm_id: str) -> list:
        b = self.data["books"].get(bid)
        if not b:
            return []
        b["bookmarks"] = [x for x in b.get("bookmarks", []) if x.get("id") != bm_id]
        self.save()
        return b["bookmarks"]

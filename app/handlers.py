"""各格式的阅读句柄：TxtBook / MdBook / EpubBook / ComicBook。

安全约定：
- EPUB 内 HTML 一律白名单净化，剥离脚本/样式/外链资源；
- 压缩包只按条目名读取，不做整包解压（Zip Slip 无入口）；
- CBR 依赖系统 UnRAR，缺失时给出明确提示，不静默失败。
"""
from __future__ import annotations

import atexit
import mimetypes
import posixpath
import re
import shutil
import tarfile
import tempfile
import zipfile
from collections import OrderedDict
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from . import textproc as tp
from .config import COMIC_IMAGE_EXTS, data_dir


class BookError(Exception):
    """面向用户的打开/阅读错误。"""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _is_image_name(name: str) -> bool:
    base = posixpath.basename(name.replace("\\", "/"))
    if base.startswith((".", "_")):
        return False
    if "__MACOSX" in name:
        return False
    return Path(base).suffix.lower() in COMIC_IMAGE_EXTS


# ------------------------------------------------------------------ TXT

class TxtBook:
    kind = "text"

    def __init__(self, path: Path):
        raw = path.read_bytes()
        self.text, self.encoding = tp.decode_bytes(raw)
        self.lines = self.text.splitlines()
        self.chapters = tp.split_chapters(self.text)
        self._cache: dict[tuple[int, str], dict] = {}

    def meta(self) -> dict:
        title = ""
        for line in self.lines[:80]:
            s = line.strip()
            if s:
                title = s[:40]
                break
        return {"title": title, "author": ""}

    def toc(self) -> list[dict]:
        return [{"title": c["title"], "index": i} for i, c in enumerate(self.chapters)]

    def chapter(self, idx: int, mode: str = "none") -> dict:
        key = (idx, mode)
        if key in self._cache:
            return self._cache[key]
        if not 0 <= idx < len(self.chapters):
            raise BookError("章节不存在")
        ch = self.chapters[idx]
        end = self.chapters[idx + 1]["start"] if idx + 1 < len(self.chapters) else len(self.lines)
        text = "\n".join(self.lines[ch["start"]:end])
        # 标题行由阅读器单独渲染成章头，正文里去掉，避免重复
        body = text.lstrip()
        if body:
            first, _, rest = body.partition("\n")
            if first.strip()[:50] == ch["title"]:
                text = rest
        text = tp.convert_text(text, mode)
        out = {
            "index": idx,
            "total": len(self.chapters),
            "title": tp.convert_text(ch["title"], mode),
            "html": tp.text_to_html(text),
        }
        if len(self._cache) > 64:
            self._cache.clear()
        self._cache[key] = out
        return out

    def search(self, keyword: str, mode: str = "none") -> list[dict]:
        kw = keyword.strip()
        if not kw:
            return []
        hits = []
        slices = tp.chapter_slices(self.lines, self.chapters)
        for i, text in enumerate(slices):
            body = tp.convert_text(text, mode)
            pos = body.find(kw)
            if pos < 0:
                continue
            start = max(0, pos - 30)
            excerpt = re.sub(r"\s+", " ", body[start:pos + len(kw) + 40])
            hits.append({"chapter": i, "title": self.chapters[i]["title"], "excerpt": excerpt})
            if len(hits) >= 100:
                break
        return hits

    def close(self):
        self._cache.clear()


# ------------------------------------------------------------------ MD

class MdBook:
    kind = "text"

    def __init__(self, path: Path):
        self.path = path
        raw = path.read_bytes()
        self.text, self.encoding = tp.decode_bytes(raw)
        self._html: dict[str, str] = {}

    def meta(self) -> dict:
        title = ""
        for line in self.text.splitlines()[:120]:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                title = s.lstrip("#").strip()
            else:
                title = s
            break
        return {"title": title[:40] or self.path.stem, "author": ""}

    def _render(self, mode: str) -> str:
        if mode in self._html:
            return self._html[mode]
        import markdown

        body = markdown.markdown(
            self.text,
            extensions=["extra", "sane_lists", "toc"],
            output_format="html",
        )
        html = tp.sanitize_html(body)
        if mode != "none":
            html = tp.convert_text(html, mode)
        self._html[mode] = html
        return html

    def toc(self, mode: str = "none") -> list[dict]:
        soup = BeautifulSoup(self._render(mode), "html.parser")
        out = []
        for h in soup.find_all(["h1", "h2", "h3"]):
            text = h.get_text().strip()
            if text:
                out.append({"title": text[:50], "anchor": h.get("id", "")})
        return out

    def chapter(self, idx: int, mode: str = "none") -> dict:
        if idx != 0:
            raise BookError("章节不存在")
        return {
            "index": 0,
            "total": 1,
            "title": self.meta()["title"],
            "html": self._render(mode),
            "anchors": self.toc(mode),
        }

    def search(self, keyword: str, mode: str = "none") -> list[dict]:
        kw = keyword.strip()
        if not kw:
            return []
        body = tp.convert_text(self.text, mode)
        pos = body.find(kw)
        if pos < 0:
            return []
        excerpt = re.sub(r"\s+", " ", body[max(0, pos - 30):pos + len(kw) + 40])
        return [{"chapter": 0, "title": self.meta()["title"], "excerpt": excerpt}]

    def close(self):
        self._html.clear()


# ------------------------------------------------------------------ EPUB

class EpubBook:
    kind = "text"

    def __init__(self, path: Path, book_id: str, private: bool = False):
        self.path = path
        self.book_id = book_id
        self.private = bool(private)
        self.zf = zipfile.ZipFile(path)
        self.cache = (
            Path(tempfile.mkdtemp(prefix="inkread-private-"))
            if self.private
            else data_dir() / "cache" / f"epub_{book_id}"
        )
        if self.private:
            atexit.register(shutil.rmtree, self.cache, True)
        self.names = {n.replace("\\", "/") for n in self.zf.namelist()}
        self._titles: list[str | None] = []
        self._html_cache: dict[tuple[int, str], dict] = {}
        try:
            self._parse()
            self._extract()
        except BookError:
            raise
        except Exception as e:
            raise BookError(f"EPUB 解析失败：{e}") from e

    # ---------- 解析
    def _read_zip(self, rel: str) -> bytes:
        rel = rel.lstrip("/")
        if rel in self.names:
            return self.zf.read(rel)
        lower = {n.lower(): n for n in self.names}
        hit = lower.get(rel.lower())
        if hit:
            return self.zf.read(hit)
        raise BookError(f"EPUB 缺少文件：{rel}")

    def _in_zip(self, rel: str) -> str:
        """OPF 内的相对路径 -> zip 内的完整路径。"""
        rel = unquote(rel or "").lstrip("/")
        if self.opf_dir:
            return posixpath.normpath(posixpath.join(self.opf_dir, rel))
        return rel

    def _parse(self):
        try:
            cont = self.zf.read("META-INF/container.xml")
            root = ET.fromstring(cont)
            opf_rel = ""
            for el in root.iter():
                if _local(el.tag) == "rootfile":
                    opf_rel = el.get("full-path") or ""
                    break
        except KeyError:
            opf_rel = ""
        if not opf_rel:
            cand = [n for n in self.names if n.lower().endswith(".opf")]
            if not cand:
                raise BookError("未找到 EPUB 的 OPF 清单")
            opf_rel = cand[0]
        self.opf_rel = opf_rel.lstrip("/")
        self.opf_dir = posixpath.dirname(self.opf_rel)
        opf = ET.fromstring(self._read_zip(self.opf_rel))

        manifest: dict[str, dict] = {}
        spine_ids: list[str] = []
        title = author = ""
        ncx_id = ""
        for el in opf.iter():
            tag = _local(el.tag)
            if tag == "item":
                manifest[el.get("id")] = {
                    "href": (el.get("href") or "").replace("\\", "/"),
                    "media": el.get("media-type") or "",
                    "props": (el.get("properties") or "").split(),
                }
            elif tag == "itemref":
                if el.get("idref"):
                    spine_ids.append(el.get("idref"))
            elif tag == "title" and not title:
                title = (el.text or "").strip()
            elif tag == "creator" and not author:
                author = (el.text or "").strip()
            elif tag == "spine":
                ncx_id = el.get("toc") or ncx_id

        self.manifest = manifest
        self.spine_ids = [i for i in spine_ids if i in manifest]
        self.title = title
        self.author = author
        self.cover_href = ""
        for el in opf.iter():
            if _local(el.tag) == "meta" and el.get("name") == "cover":
                cid = el.get("content")
                if cid in manifest:
                    self.cover_href = manifest[cid]["href"]
                    break
        if not self.cover_href:
            for it in manifest.values():
                if "cover-image" in it["props"]:
                    self.cover_href = it["href"]
                    break

        self.spine_rels = [unquote(manifest[i]["href"]).lstrip("/") for i in self.spine_ids]
        self.rel_index = {rel: i for i, rel in enumerate(self.spine_rels)}

        # 目录（epub3 nav 优先，退化 epub2 ncx）
        self.nav: list[tuple[str, str]] = []
        nav_item = next((it for it in manifest.values() if "nav" in it["props"]), None)
        if nav_item:
            self._parse_nav(nav_item["href"])
        elif ncx_id and ncx_id in manifest:
            self._parse_ncx(manifest[ncx_id]["href"])

        # 章节标题
        self._titles = [None] * len(self.spine_rels)
        nav_dir = posixpath.dirname(unquote((nav_item or {}).get("href", ""))) if nav_item else ""
        for label, href in self.nav:
            rel = href.split("#")[0]
            if not rel:
                continue
            target = posixpath.normpath(posixpath.join(nav_dir, unquote(rel))) if nav_dir else unquote(rel)
            j = self.rel_index.get(target)
            if j is not None and not self._titles[j]:
                self._titles[j] = label[:50]
        if not any(self._titles):
            self._titles = [None] * len(self.spine_rels)

    def _parse_nav(self, nav_href: str):
        soup = BeautifulSoup(self._read_zip(self._in_zip(nav_href)), "html.parser")
        nav = soup.find("nav", attrs={"epub:type": "toc"}) or soup.find("nav")
        if not nav:
            return
        for a in nav.find_all("a", href=True):
            self.nav.append(((a.get_text() or "").strip()[:50], a["href"]))

    def _parse_ncx(self, ncx_href: str):
        try:
            root = ET.fromstring(self._read_zip(self._in_zip(ncx_href)))
        except Exception:
            return
        for np_ in root.iter():
            if _local(np_.tag) != "navPoint":
                continue
            label = ""
            src = ""
            for child in np_.iter():
                t = _local(child.tag)
                if t == "text" and not label:
                    label = (child.text or "").strip()
                elif t == "content" and not src:
                    src = child.get("src") or ""
            if src:
                self.nav.append((label[:50], src))

    def _extract(self):
        if self.cache.exists() and not self.private:
            return
        self.cache.mkdir(parents=True, exist_ok=True)
        wanted = {unquote(it["href"]).lstrip("/") for it in self.manifest.values()}
        for info in self.zf.infolist():
            name = info.filename.replace("\\", "/")
            if info.is_dir() or name.startswith("META-INF") or "__MACOSX" in name:
                continue
            if name.startswith("/") or ".." in name.split("/"):
                continue
            if (info.external_attr >> 16) & 0o170000 == 0o120000:  # 符号链接，跳过
                continue
            if self.opf_dir:
                if not name.startswith(self.opf_dir + "/"):
                    continue
                rel = name[len(self.opf_dir) + 1:]
            else:
                rel = name
            if rel not in wanted:
                continue
            dest = self.cache / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with self.zf.open(info) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)

    # ---------- 阅读
    def meta(self) -> dict:
        return {"title": self.title or self.path.stem, "author": self.author}

    def toc(self) -> list[dict]:
        out = []
        for i in range(len(self.spine_rels)):
            title = self._titles[i] if i < len(self._titles) else None
            out.append({"title": title or f"第 {i + 1} 节", "index": i})
        return out

    def chapter(self, idx: int, mode: str = "none") -> dict:
        key = (idx, mode)
        if key in self._html_cache:
            return self._html_cache[key]
        if not 0 <= idx < len(self.spine_rels):
            raise BookError("章节不存在")
        rel = self.spine_rels[idx]
        f = self.cache / rel
        if not f.exists():
            raise BookError(f"章节文件缺失：{rel}")
        soup = BeautifulSoup(f.read_bytes(), "html.parser")
        body = soup.body or soup
        for t in body.find_all(["script", "style"]):
            t.decompose()

        base_dir = posixpath.dirname(rel)
        for tag in body.find_all(["img", "image"]):
            src = tag.get("src") or tag.get("xlink:href") or tag.get("href") or ""
            src = unquote(src.split("#")[0])
            if not src:
                continue
            if src.startswith(("http://", "https://", "data:", "//")):
                tag["src"] = ""
                continue
            target = posixpath.normpath(posixpath.join(base_dir, src)) if base_dir else posixpath.normpath(src)
            if target.startswith(".."):
                continue
            tag["src"] = f"/api/book/{self.book_id}/asset/{target}"
            if tag.name == "image":
                tag.name = "img"

        for a in body.find_all("a", href=True):
            href = a["href"]
            if href.startswith(("http://", "https://", "mailto:", "javascript:")):
                continue
            frag = ""
            if "#" in href:
                href, frag = href.split("#", 1)
            if not href:
                a["data-goto"] = frag
                a["href"] = ""
                continue
            target = posixpath.normpath(posixpath.join(base_dir, unquote(href))) if base_dir else unquote(href)
            j = self.rel_index.get(target)
            if j is None:
                a["data-goto"] = "0"
            else:
                a["data-goto"] = f"{j}:{frag}" if frag else str(j)
            a["href"] = ""

        title = self._titles[idx] if idx < len(self._titles) else None
        if not title:
            h = body.find(["h1", "h2", "h3"])
            title = (h.get_text().strip()[:50] if h else f"第 {idx + 1} 节")
            if idx < len(self._titles):
                self._titles[idx] = title

        html = tp.sanitize_html(body.decode_contents())
        if mode != "none":
            html = tp.convert_text(html, mode)
        out = {
            "index": idx,
            "total": len(self.spine_rels),
            "title": tp.convert_text(title, mode),
            "html": html,
        }
        if len(self._html_cache) > 48:
            self._html_cache.clear()
        self._html_cache[key] = out
        return out

    def search(self, keyword: str, mode: str = "none") -> list[dict]:
        kw = keyword.strip()
        if not kw:
            return []
        hits = []
        for i, rel in enumerate(self.spine_rels):
            f = self.cache / rel
            if not f.exists():
                continue
            soup = BeautifulSoup(f.read_bytes(), "html.parser")
            for t in soup.find_all(["script", "style"]):
                t.decompose()
            text = tp.convert_text(soup.get_text(" "), mode)
            pos = text.find(kw)
            if pos < 0:
                continue
            excerpt = re.sub(r"\s+", " ", text[max(0, pos - 30):pos + len(kw) + 40])
            hits.append({"chapter": i, "title": self.toc()[i]["title"], "excerpt": excerpt})
            if len(hits) >= 100:
                break
        return hits

    def cover_bytes(self) -> tuple[bytes, str] | None:
        if not self.cover_href:
            return None
        rel = unquote(self.cover_href).lstrip("/")
        f = self.cache / rel
        if not f.exists():
            return None
        ctype = mimetypes.guess_type(rel)[0] or "image/jpeg"
        return f.read_bytes(), ctype

    def close(self):
        try:
            self.zf.close()
        except Exception:
            pass
        self._html_cache.clear()
        if self.private:
            try:
                shutil.rmtree(self.cache, ignore_errors=True)
            except Exception:
                pass


# ------------------------------------------------------------------ 漫画

def _find_rar_tool() -> str | None:
    for exe in ("unrar", "unar"):
        p = shutil.which(exe)
        if p:
            return p
    for p in (
        r"C:\Program Files\WinRAR\UnRAR.exe",
        r"C:\Program Files (x86)\WinRAR\UnRAR.exe",
        r"C:\Program Files\WinRAR\Rar.exe",
    ):
        if Path(p).exists():
            return p
    return None


class ComicBook:
    kind = "comic"

    def __init__(self, path: Path, book_id: str):
        self.path = path
        self.book_id = book_id
        self.mode = "folder" if path.is_dir() else path.suffix.lower().lstrip(".")
        self._zf: zipfile.ZipFile | None = None
        self._tar: tarfile.TarFile | None = None
        self._rar = None
        self._7z = None
        self._load_names()

    def _load_names(self):
        if self.mode == "folder":
            files = [p for p in self.path.iterdir() if p.is_file() and _is_image_name(p.name)]
            files.sort(key=lambda p: tp.natural_key(p.name))
            self.pages = [p.name for p in files]
        elif self.mode in ("cbz", "zip"):
            self._zf = zipfile.ZipFile(self.path)
            self.pages = sorted(
                (i.filename for i in self._zf.infolist() if not i.is_dir() and _is_image_name(i.filename)),
                key=tp.natural_key,
            )
        elif self.mode in ("cb7", "7z"):
            import py7zr

            self._7z = py7zr.SevenZipFile(self.path, "r")
            if self._7z.needs_password():
                raise BookError("加密的 7z 压缩包暂不支持")
            self._7z_dir = data_dir() / "cache" / f"sevenz_{self.book_id}"
            self.pages = sorted((n for n in self._7z.getnames() if _is_image_name(n)), key=tp.natural_key)
        elif self.mode in ("cbr", "rar"):
            import rarfile

            tool = _find_rar_tool()
            if not tool:
                raise BookError("读取 CBR/RAR 需要 UnRAR（WinRAR 安装目录自带）或 unar，请先安装其中之一")
            rarfile.UNRAR_TOOL = tool
            self._rar = rarfile.RarFile(self.path)
            self.pages = sorted((n for n in self._rar.namelist() if _is_image_name(n)), key=tp.natural_key)
        elif self.mode in ("cbt", "tar"):
            self._tar = tarfile.open(self.path, "r:*")
            self.pages = sorted(
                (m.name for m in self._tar.getmembers() if m.isfile() and _is_image_name(m.name)),
                key=tp.natural_key,
            )
        else:
            raise BookError(f"暂不支持的压缩格式：.{self.mode}")
        if not self.pages:
            raise BookError("压缩包内没有找到图片页面")

    def meta(self) -> dict:
        name = self.path.name
        title = re.sub(r"\s*[\[（(][^\]）)]*[\]）)]\s*", " ", name).strip()
        title = Path(title).stem or name
        return {"title": title[:60], "author": ""}

    def toc(self) -> list[dict]:
        return [{"title": f"第 {i + 1} 页", "index": i} for i in range(len(self.pages))]

    def chapter(self, idx: int, mode: str = "none") -> dict:
        raise BookError("漫画不分章节")

    def page_count(self) -> int:
        return len(self.pages)

    def page(self, n: int) -> tuple[bytes, str]:
        if not 0 <= n < len(self.pages):
            raise BookError("页码超出范围")
        name = self.pages[n]
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        if self.mode == "folder":
            return (self.path / name).read_bytes(), ctype
        if self._zf is not None:
            return self._zf.read(name), ctype
        if self._7z is not None:
            dest = self._7z_dir / name
            if not dest.exists():
                try:
                    self._7z_dir.mkdir(parents=True, exist_ok=True)
                    self._7z.reset()
                    self._7z.extract(path=self._7z_dir, targets=[name])
                except Exception as e:
                    raise BookError(f"7z 解压失败：{e}") from e
            if not dest.exists():
                raise BookError(f"7z 中找不到页面：{name}")
            return dest.read_bytes(), ctype
        if self._rar is not None:
            return self._rar.read(name), ctype
        if self._tar is not None:
            m = self._tar.getmember(name)
            f = self._tar.extractfile(m)
            return (f.read() if f else b""), ctype
        raise BookError("漫画文件未打开")

    def close(self):
        for closer in (self._zf, self._tar, self._rar, self._7z):
            try:
                if closer is not None:
                    closer.close()
            except Exception:
                pass


# ------------------------------------------------------------------ 注册表（LRU）

def open_handle(meta: dict):
    kind = meta["kind"]
    path = Path(meta["path"])
    if kind == "txt":
        return TxtBook(path)
    if kind == "md":
        return MdBook(path)
    if kind == "epub":
        return EpubBook(path, meta["id"], private=bool(meta.get("private")))
    if kind == "comic":
        return ComicBook(path, meta["id"])
    raise BookError(f"未知的书籍类型：{kind}")


class Registry:
    """按需打开阅读句柄，限制同时在内存中的数量。"""

    def __init__(self, cap: int = 10):
        self.cap = cap
        self._d: OrderedDict[str, object] = OrderedDict()

    def get(self, meta: dict):
        bid = meta["id"]
        if bid in self._d:
            self._d.move_to_end(bid)
            return self._d[bid]
        handle = open_handle(meta)
        self._d[bid] = handle
        while len(self._d) > self.cap:
            _, old = self._d.popitem(last=False)
            try:
                old.close()
            except Exception:
                pass
        return handle

    def drop(self, bid: str):
        h = self._d.pop(bid, None)
        if h is not None:
            try:
                h.close()
            except Exception:
                pass

"""文本处理：编码识别、章节分割、繁简转换、HTML 净化、自然排序。"""
from __future__ import annotations

import html as _html
import posixpath
import re
from functools import lru_cache
from urllib.parse import unquote

import bleach

# ---------------------------------------------------------------- 编码识别

_BOMS = (
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
)

# 简体/繁体特征字，用于在 gb18030 与 big5 之间做倾向判断
_SIMP_MARKS = set("们来过实现后里开关发数学业时说当为无还没")
_TRAD_MARKS = set("們過來實現後裡開關發數學業說時當為無還沒")


def _cn_tilt(text: str) -> int:
    """正数偏简体，负数偏繁体。"""
    s = sum(text.count(c) for c in _SIMP_MARKS)
    t = sum(text.count(c) for c in _TRAD_MARKS)
    return s - t


def detect_encoding(raw: bytes) -> str:
    for bom, enc in _BOMS:
        if raw.startswith(bom):
            return enc
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    best = None
    for enc in ("gb18030", "big5"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        tilt = _cn_tilt(text)
        if enc == "gb18030" and tilt < -30:
            continue  # gbk 解出来却满是繁体特征字，可能是 Big5 文件
        if best is None or abs(tilt) > abs(best[1]):
            best = (enc, tilt)
    if best:
        return best[0]
    return "latin-1"


def decode_bytes(raw: bytes) -> tuple[str, str]:
    enc = detect_encoding(raw)
    return raw.decode(enc, errors="replace"), enc


# ---------------------------------------------------------------- 章节分割

_CHAPTER_RES = [
    re.compile(r"^\s*第[0-9零〇一二三四五六七八九十百千两]+[卷回部篇集章话节]\s*[：:、．.－-]?\s*\S.*$"),
    re.compile(r"^\s*(序|序章|序言|楔子|前言|引子|终章|尾声|后记|番外篇?)\s*[：:、．.]?\s*\S.*$"),
    re.compile(r"^\s*[Cc]hapter\s+\d+.*$"),
    re.compile(r"^\s*CHAPTER\s+[0-9IVXLC]+.*$"),
    re.compile(r"^\s*#\s+\S.*$"),
]


def split_chapters(text: str, limit: int = 6000) -> list[dict]:
    """返回 [{title, start}]，start 为行号。识别不出章节时返回单章。"""
    lines = text.splitlines()
    marks: list[tuple[int, str]] = []
    for i, line in enumerate(lines[:limit]):
        for rx in _CHAPTER_RES:
            if rx.match(line):
                title = line.strip()
                marks.append((i, title[:50]))
                break
    if len(marks) < 2:
        return [{"title": "正文", "start": 0}]
    chapters: list[dict] = []
    if marks[0][0] > 0:
        chapters.append({"title": "卷首", "start": 0})
    chapters.extend({"title": t, "start": ln} for ln, t in marks)
    return chapters


def chapter_slices(lines: list[str], chapters: list[dict]) -> list[str]:
    out = []
    for i, ch in enumerate(chapters):
        end = chapters[i + 1]["start"] if i + 1 < len(chapters) else len(lines)
        out.append("\n".join(lines[ch["start"]:end]))
    return out


# ---------------------------------------------------------------- 繁简转换

_VALID_MODES = {
    "none", "s2t", "t2s", "s2tw", "tw2s", "s2hk", "hk2s", "t2tw", "t2hk",
}


@lru_cache(maxsize=8)
def _opencc(mode: str):
    from opencc import OpenCC

    return OpenCC(mode)


def convert_text(text: str, mode: str = "none") -> str:
    if not text or mode not in _VALID_MODES or mode == "none":
        return text
    try:
        return _opencc(mode).convert(text)
    except Exception:
        return text


# ---------------------------------------------------------------- HTML 净化

ALLOWED_TAGS = [
    "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "em", "b", "i", "u", "s", "small", "mark", "sub", "sup",
    "blockquote", "q", "cite", "abbr", "code", "pre", "kbd", "samp", "var",
    "ul", "ol", "li", "dl", "dt", "dd",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
    "span", "div", "section", "article", "aside", "header", "footer", "main",
    "figure", "figcaption", "img", "a", "details", "summary", "time",
]
ALLOWED_ATTRS = {
    "a": ["href", "title", "data-goto"],
    "img": ["src", "alt", "title", "width", "height"],
    "td": ["colspan", "rowspan", "align"],
    "th": ["colspan", "rowspan", "align", "scope"],
    "ol": ["start"],
}

_EXTERNAL_IMG = re.compile(r'(<img\b[^>]*?\bsrc=")https?://[^"]*(")', re.I)


def sanitize_html(raw: str) -> str:
    """白名单净化，剥掉脚本/事件属性/样式；外链图片置空（离线阅读，防跟踪）。"""
    cleaned = bleach.clean(
        raw,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=["http", "https"],
        strip=True,
    )
    return _EXTERNAL_IMG.sub(r"\1\2", cleaned)


def text_to_html(text: str) -> str:
    """纯文本 -> 段落 HTML。无空行时按单行分段（适配小说网文章式）。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip("\ufeff ")
    if not text.strip():
        return "<p></p>"
    has_blank = re.search(r"\n[ \t]*\n", text) is not None
    parts = re.split(r"\n[ \t]*\n", text) if has_blank else text.split("\n")
    out = []
    for part in parts:
        if not part.strip():
            continue
        out.append("<p>" + _html.escape(part) + "</p>")
    return "".join(out) or "<p></p>"


# ---------------------------------------------------------------- 路径工具

def safe_join(root: str, rel: str) -> str | None:
    """把归档内的相对路径安全地拼到 root 下，越界返回 None（防 Zip Slip）。"""
    rel = unquote(rel or "").replace("\\", "/").lstrip("/")
    if not rel or rel.startswith("../") or "/../" in rel or ".." in rel.split("/"):
        return None
    full = posixpath.normpath(posixpath.join(root, rel))
    if full != root and not full.startswith(root.rstrip("/") + "/"):
        return None
    return full


def natural_key(name: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]

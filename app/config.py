"""墨读 InkRead —— 本地电子书与漫画阅读器

路径与常量。所有数据均存放于本地，不进行任何网络请求。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_ID = "InkRead"
APP_NAME = "墨读"
VERSION = "1.0.0"

# 扩展名 -> 类型
TEXT_EXTS = {"txt": "txt", "md": "md", "markdown": "md"}
COMIC_EXTS = {
    "cbz": "comic", "zip": "comic",
    "cbr": "comic", "rar": "comic",
    "cb7": "comic", "7z": "comic",
    "cbt": "comic", "tar": "comic",
}
EPUB_EXTS = {"epub": "epub"}

COMIC_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def classify(path: str) -> str | None:
    """按扩展名判断文件类型；目录视为漫画（图片文件夹）。"""
    p = Path(path)
    if p.is_dir():
        return "comic"
    ext = p.suffix.lower().lstrip(".")
    if ext in TEXT_EXTS:
        return TEXT_EXTS[ext]
    if ext in EPUB_EXTS:
        return "epub"
    if ext in COMIC_EXTS:
        return "comic"
    return None


def bundle_dir() -> Path:
    """只读资源目录（打包后为 _MEIPASS，开发时为工程根目录）。"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """可写数据目录。设置 INKREAD_HOME 可强制指定（便携模式）。"""
    env = os.environ.get("INKREAD_HOME")
    if env:
        base = Path(env)
    else:
        base = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_ID
    (base / "cache" / "covers").mkdir(parents=True, exist_ok=True)
    return base


def web_dir() -> Path:
    return bundle_dir() / "web"

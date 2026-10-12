"""暴露给前端的原生能力：文件对话框、窗口控制、外部链接。

注意：本类的**所有公开属性都会被 pywebview 递归展开**成 JS 桥
（webview/util.py 的 get_functions 会遍历 dir(obj) 并对非函数属性递归），
一旦持有 Window / .NET 对象就会陷入无限属性遍历并长期占用 GIL，导致窗口卡死。
因此这里只允许出现方法，窗口对象一律通过模块级 webview.windows 获取。
"""
from __future__ import annotations

import os
import webbrowser
from urllib.parse import urlparse

FILE_TYPES = (
    "电子书与漫画 (*.txt;*.md;*.markdown;*.epub;*.cbz;*.zip;*.cbr;*.rar;*.cb7;*.7z;*.cbt;*.tar)",
    "所有文件 (*.*)",
)

# 窗口引用存在模块级，**不能**挂在 JsApi 实例上：
# pywebview 会递归展开 js_api 的所有公开属性，持有 Window / .NET 对象会导致窗口卡死。
_WINDOW = None


def set_window(window) -> None:
    """由 main.py 在创建窗口后调用。"""
    global _WINDOW
    _WINDOW = window


def _window():
    """取当前窗口：优先 pywebview 的窗口列表，取不到时用建窗时记下的引用。"""
    import webview

    try:
        if webview.windows:
            return webview.windows[0]
    except Exception:
        pass
    return _WINDOW


def _dlg(name: str):
    """取对话框常量，优先用新版 FileDialog，兼容旧版 OPEN_DIALOG。"""
    import webview

    fd = getattr(webview, "FileDialog", None)
    if fd is not None:
        return getattr(fd, name)
    return getattr(webview, name)


class JsApi:
    def open_files(self) -> list:
        w = _window()
        if w is None:
            return []
        result = w.create_file_dialog(_dlg("OPEN"), allow_multiple=True, file_types=FILE_TYPES)
        return [str(x) for x in result] if result else []

    def open_folder(self):
        w = _window()
        if w is None:
            return None
        result = w.create_file_dialog(_dlg("FOLDER"))
        return str(result) if result else None

    def open_external(self, url: str) -> bool:
        u = urlparse(url or "")
        if u.scheme in ("http", "https") and u.hostname:
            webbrowser.open(url)
            return True
        return False

    def open_data_dir(self) -> str:
        from .config import data_dir

        d = str(data_dir())
        if os.name == "nt":
            os.startfile(d)  # noqa: S606
        return d

    def window_action(self, action: str):
        from . import win32

        if action == "minimize":
            win32.minimize()
        elif action == "toggle-maximize":
            win32.toggle_maximize()
        elif action == "close":
            win32.close()
        elif action == "fullscreen":
            w = _window()
            if w is not None:
                w.toggle_fullscreen()
        elif action == "bounds":
            return win32.bounds()

    def window_bounds(self) -> dict:
        """窗口位置与大小（Win32 物理像素），前端用于边缘缩放。"""
        from . import win32

        return win32.bounds()

    def window_set_bounds(self, x, y, w, h) -> bool:
        from . import win32

        try:
            win32.set_bounds(int(x), int(y), int(w), int(h))
            return True
        except Exception:
            return False

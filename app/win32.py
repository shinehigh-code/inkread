"""Win32 窗口操作。

无边框窗口没有系统边框，pywebview 的 maximize/restore 也不够可靠，
这里直接调 Win32：最大化 = 铺满工作区（不遮任务栏）并记住原尺寸，还原 = 回到原尺寸，
另外提供位置/大小查询与设置，供前端做边缘拖拽缩放。
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SW_MINIMIZE = 6
SW_RESTORE = 9
WM_CLOSE = 0x0010
SPI_GETWORKAREA = 0x0030

_prev: dict | None = None
_hwnd_cache = 0


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def hwnd() -> int:
    """取本进程的可见顶层窗口句柄。"""
    global _hwnd_cache
    if _hwnd_cache and user32.IsWindow(_hwnd_cache):
        return _hwnd_cache
    pid = os.getpid()
    found: list[int] = []

    def cb(h, _lp):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(wpid))
        if wpid.value == pid and user32.IsWindowVisible(h) and user32.GetWindowTextLengthW(h) > 0:
            found.append(h)
        return True

    user32.EnumWindows(ENUMPROC(cb), 0)
    _hwnd_cache = found[0] if found else 0
    return _hwnd_cache


def bounds() -> dict:
    h = hwnd()
    if not h:
        return {"x": 0, "y": 0, "w": 0, "h": 0, "dpi": 96, "maximized": False}
    r = RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    dpi = 96
    try:
        dpi = int(user32.GetDpiForWindow(h)) or 96
    except Exception:
        pass
    return {
        "x": r.left,
        "y": r.top,
        "w": r.right - r.left,
        "h": r.bottom - r.top,
        "dpi": dpi,
        "maximized": is_maximized(),
    }


def work_area() -> dict:
    r = RECT()
    if not user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(r), 0):
        return {"x": 0, "y": 0, "w": 1920, "h": 1080}
    return {"x": r.left, "y": r.top, "w": r.right - r.left, "h": r.bottom - r.top}


def set_bounds(x: int, y: int, w: int, h: int) -> None:
    h_ = hwnd()
    if not h_:
        return
    user32.SetWindowPos(h_, 0, int(x), int(y), int(w), int(h), SWP_NOZORDER | SWP_NOACTIVATE)


def is_maximized() -> bool:
    h = hwnd()
    if not h:
        return False
    if user32.IsZoomed(h):
        return True
    b, wa = bounds_raw(), work_area()
    return (
        abs(b[0] - wa["x"]) <= 4
        and abs(b[1] - wa["y"]) <= 4
        and abs(b[2] - wa["w"]) <= 8
        and abs(b[3] - wa["h"]) <= 8
    )


def bounds_raw() -> tuple[int, int, int, int]:
    h = hwnd()
    if not h:
        return (0, 0, 0, 0)
    r = RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def toggle_maximize() -> bool:
    """切换最大化/还原，返回切换后是否处于最大化。"""
    global _prev
    h = hwnd()
    if not h:
        return False
    if is_maximized():
        if _prev:
            set_bounds(_prev["x"], _prev["y"], _prev["w"], _prev["h"])
            _prev = None
        else:
            user32.ShowWindow(h, SW_RESTORE)
        return False
    x, y, w, hh = bounds_raw()
    if w > 200 and hh > 150:
        _prev = {"x": x, "y": y, "w": w, "h": hh}
    wa = work_area()
    set_bounds(wa["x"], wa["y"], wa["w"], wa["h"])
    return True


def minimize() -> None:
    h = hwnd()
    if h:
        user32.ShowWindow(h, SW_MINIMIZE)


def close() -> None:
    h = hwnd()
    if h:
        user32.PostMessageW(h, WM_CLOSE, 0, 0)


def forget_prev() -> None:
    """窗口被手动调整过大小后，清掉还原用的记录。"""
    global _prev
    _prev = None

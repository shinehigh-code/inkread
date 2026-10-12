"""进程内自检（INKREAD_DIAG=1 时启用）。

用于排查「窗口卡死」：定时探测本进程主窗口是否响应、记录窗口尺寸/DPI，
并在前台无响应时把全部线程的 Python 栈写进日志。
"""
from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

from .log import log

SMTO_ABORTIFHUNG = 0x0002
WM_NULL = 0x0000
user32 = ctypes.WinDLL("user32", use_last_error=True)
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _own_windows() -> list[tuple[int, str, tuple[int, int, int, int]]]:
    pid = os.getpid()
    out = []

    def cb(hwnd, _lp):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != pid or not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 2)
        user32.GetWindowTextW(hwnd, buf, n + 2)
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        out.append((hwnd, buf.value, (r.left, r.top, r.right - r.left, r.bottom - r.top)))
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def _responsive(hwnd: int, timeout_ms: int = 2500) -> bool:
    res = ctypes.c_size_t()
    r = user32.SendMessageTimeoutW(hwnd, WM_NULL, 0, 0, SMTO_ABORTIFHUNG, timeout_ms, ctypes.byref(res))
    return bool(r)


def start(timeout_seconds: int = 25):
    try:
        import faulthandler

        log_path = None
        from .config import data_dir

        log_path = data_dir() / "inkread.log"
        # C 级看门狗：超时未结束时打印全部线程栈（进程继续运行）
        faulthandler.dump_traceback_later(timeout_seconds, repeat=True, file=open(log_path, "a", encoding="utf-8"))
        log(f"[自检] faulthandler 看门狗已启动（{timeout_seconds}s 间隔）")
    except Exception as e:
        log(f"[自检] faulthandler 启动失败：{e}")

    def worker():
        beat = 0
        hwnd = 0
        captured = False
        while True:
            beat += 1
            try:
                if not hwnd:
                    wins = _own_windows()
                    if wins:
                        hwnd, title, rect = wins[0]
                        try:
                            dpi = user32.GetDpiForWindow(hwnd) if hasattr(user32, "GetDpiForWindow") else 0
                        except Exception:
                            dpi = 0
                        log(f"[自检] 找到窗口 hwnd={hwnd} 标题={title!r} 外框={rect} DPI={dpi}")
                if hwnd:
                    ok = _responsive(hwnd)
                    log(f"[自检] 心跳#{beat} 响应={'是' if ok else '否'} 线程数={threading.active_count()}")
                    if beat >= 3 and not captured and os.environ.get("INKREAD_CAPTURE"):
                        captured = _capture(hwnd)
                    if beat == 5 and os.environ.get("INKREAD_SELFTEST"):
                        _test_bridge()
                else:
                    log(f"[自检] 心跳#{beat} 尚未找到窗口，线程数={threading.active_count()}")
            except Exception as e:
                log(f"[自检] 心跳异常：{e}")
            time.sleep(5)

    threading.Thread(target=worker, name="inkread-diag", daemon=True).start()


def _test_bridge():
    """实测原生桥：取窗口、文件对话框能力、最大化/还原是否真的改变窗口尺寸。"""
    try:
        import webview

        from . import win32
        from .api import JsApi

        w = webview.windows[0] if webview.windows else None
        from .api import _window

        w2 = _window()
        log(f"[自检] webview.windows 长度={len(webview.windows)}；_window() 取到="
            f"{type(w2).__name__ if w2 else None}；"
            f"create_file_dialog={'有' if w2 is not None and hasattr(w2, 'create_file_dialog') else '无'}")
        if w2 is not None and w is None:
            log("[自检] 注意：pywebview 的 windows 列表在本线程为空，已由模块级兜底引用接管")
        if w is not None:
            try:
                # 语音引擎要调用一次 getVoices 才会初始化，先预热再读
                w.evaluate_js("window.speechSynthesis && speechSynthesis.getVoices()")
                time.sleep(1.2)
                n = w.evaluate_js("(window.speechSynthesis && speechSynthesis.getVoices().length) || 0")
                log(f"[自检] 系统可用语音数：{n}")
            except Exception as e:
                log(f"[自检] 语音枚举失败：{e}")

        api = JsApi()
        orig = win32.bounds()
        # 先把窗口缩到中等尺寸，否则窗口本来就接近工作区大小时，最大化看不出变化
        api.window_set_bounds(120, 120, 1180, 760)
        time.sleep(0.7)
        b0 = win32.bounds()
        api.window_action("toggle-maximize")
        time.sleep(0.9)
        b1 = win32.bounds()
        api.window_action("toggle-maximize")
        time.sleep(0.9)
        b2 = win32.bounds()
        grew = (b1["w"] * b1["h"]) > (b0["w"] * b0["h"]) * 1.15
        back = abs(b2["w"] - b0["w"]) <= 8 and abs(b2["h"] - b0["h"]) <= 8
        log(f"[自检] 窗口缩放实测：{b0['w']}x{b0['h']} → 最大化 {b1['w']}x{b1['h']} → 还原 {b2['w']}x{b2['h']}"
            f"；变大={grew} 还原准确={back}")

        # 边缘拖拽缩放走的是 window_set_bounds，这里直接验一下
        # 注意窗口有最小尺寸（960x600 逻辑像素，125% 缩放下约 1200x750 物理像素），测试值要在最小尺寸之上
        api.window_set_bounds(120, 120, 1500, 900)
        time.sleep(0.6)
        b3 = win32.bounds()
        api.window_set_bounds(120, 120, 1240, 790)
        time.sleep(0.6)
        b4 = win32.bounds()
        shrunk = b4["w"] < b3["w"] - 40 and b4["h"] < b3["h"] - 40
        log(f"[自检] 缩放接口实测：{b3['w']}x{b3['h']} → {b4['w']}x{b4['h']}；生效={shrunk}")
        log("[自检] 原生桥实测" + ("通过" if (grew and back and shrunk) else "异常") + "：最大化/还原/缩放")
        if orig["w"] > 0:  # 还原到自检前的窗口尺寸
            api.window_set_bounds(orig["x"], orig["y"], orig["w"], orig["h"])
    except Exception as e:
        log(f"[自检] 原生桥实测失败：{type(e).__name__}: {e}")


def _capture(hwnd: int) -> bool:
    """把窗口区域截屏存盘，用于确认实际渲染效果（目录可用 INKREAD_CAPTURE_DIR 指定）。"""
    try:
        from PIL import ImageGrab

        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        box = (r.left, r.top, r.right, r.bottom)
        if box[2] - box[0] < 50 or box[3] - box[1] < 50:
            return False
        out_dir = Path(os.environ.get("INKREAD_CAPTURE_DIR") or Path.cwd())
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "window.png"
        ImageGrab.grab(bbox=box, all_screens=True).save(path)
        log(f"[自检] 已截取窗口到 {path} 区域={box}")
        return True
    except Exception as e:
        log(f"[自检] 截屏失败：{e}")
        return False

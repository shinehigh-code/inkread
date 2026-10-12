"""诊断：从外部检测墨读窗口是否响应，并观察各线程 CPU 占用。

用法：python samples/diag_hang.py [exe路径]
不传参数则用源码模式启动 main.py。
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

SMTO_ABORTIFHUNG = 0x0002
WM_NULL = 0x0000

user32 = ctypes.WinDLL("user32", use_last_error=True)
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def find_windows(pid: int) -> list[tuple[int, str, tuple[int, int, int, int]]]:
    found = []

    def cb(hwnd, _lparam):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != pid:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 2)
        user32.GetWindowTextW(hwnd, buf, n + 2)
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        found.append((hwnd, buf.value, (rect.left, rect.top, rect.right, rect.bottom)))
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return found


def responsive(hwnd: int, timeout_ms: int = 2000) -> bool:
    res = ctypes.c_size_t()
    r = user32.SendMessageTimeoutW(hwnd, WM_NULL, 0, 0, SMTO_ABORTIFHUNG, timeout_ms, ctypes.byref(res))
    return bool(r)


def main():
    import psutil

    env = dict(os.environ)
    env["INKREAD_HOME"] = str(ROOT / ".diagdata")
    env["INKREAD_DEBUG"] = "1"

    if len(sys.argv) > 1:
        cmd = [sys.argv[1]]
    else:
        cmd = [PY, str(ROOT / "main.py")]

    print("启动:", " ".join(cmd), flush=True)
    proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env)
    p = psutil.Process(proc.pid)

    hwnd = None
    t0 = time.time()
    while time.time() - t0 < 30 and hwnd is None:
        time.sleep(1)
        wins = find_windows(proc.pid)
        if wins:
            hwnd, title, rect = wins[0]
            print(f"找到窗口 pid={proc.pid} hwnd={hwnd} title={title!r} rect={rect}", flush=True)

    if hwnd is None:
        print("!! 30 秒内没有找到窗口，进程还活着?", p.is_running(), flush=True)
        proc.kill()
        return

    print("\n时间   响应  内存MB  各线程CPU增量", flush=True)
    prev = {}
    for i in range(12):
        ok = responsive(hwnd, 2500)
        try:
            mem = round(p.memory_info().rss / 1048576, 1)
            threads = p.threads()
        except Exception as e:
            print("进程状态读取失败:", e, flush=True)
            break
        deltas = []
        for t in threads:
            key = t.id
            cpu = t.user_time + t.system_time
            d = cpu - prev.get(key, cpu)
            prev[key] = cpu
            if d > 0:
                deltas.append(f"tid{t.id}:{d:.2f}s")
        print(f"{i * 3:>3}s  {'是' if ok else '否'}   {mem:>6}   {' '.join(deltas) or '-'}", flush=True)
        if not ok and i > 1:
            print(">>> 窗口无响应", flush=True)
        time.sleep(3)

    print("\n线程总数:", len(p.threads()), "  子进程:", [c.name() for c in p.children()][:6], flush=True)
    try:
        proc.terminate()
    except Exception:
        pass


if __name__ == "__main__":
    main()

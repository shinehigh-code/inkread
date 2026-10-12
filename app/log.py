"""运行日志：写文件，便于排查（打包后无控制台）。"""
from __future__ import annotations

import sys
import threading
import time
import traceback
from pathlib import Path

from .config import data_dir

_lock = threading.Lock()


def log_path() -> Path:
    return data_dir() / "inkread.log"


def log(msg: str):
    try:
        with _lock:
            with open(log_path(), "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass
    try:
        print(msg, flush=True)
    except Exception:
        pass


def install_hooks():
    """把未捕获异常写进日志。"""
    def excepthook(exc_type, exc, tb):
        log("未捕获异常：\n" + "".join(traceback.format_exception(exc_type, exc, tb)))

    sys.excepthook = excepthook

    def thread_hook(args):
        log("线程异常：\n" + "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))

    threading.excepthook = thread_hook

"""结束本项目相关的进程（墨读.exe / main.py / run_dev.py）。

写成独立文件而不是内联脚本，避免「命令行里含关键字把自身也杀掉」。
用法：python tools/kill_app.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psutil

SELF = os.getpid()


def main():
    killed = []
    for p in psutil.process_iter(["pid", "name", "cmdline", "exe"]):
        pid = p.info["pid"]
        if pid == SELF:
            continue
        try:
            name = (p.info.get("name") or "").lower()
            exe = (p.info.get("exe") or "")
            args = p.info.get("cmdline") or []
            hit = False
            if exe.lower().endswith("墨读.exe") or exe.lower().endswith("墨读dbg.exe"):
                hit = True
            elif args:
                # 不能只看最后一个参数：带文件启动时最后一个是书路径（main.py 后面跟书）
                joined = [str(a).lower().replace("/", "\\") for a in args]
                if any(a.endswith("main.py") or a.endswith("run_dev.py") for a in joined):
                    # 只认本项目的脚本
                    if any("inkread" in a for a in joined):
                        hit = True
            if hit:
                killed.append((pid, name))
                p.kill()
        except Exception:
            continue
    print("已结束:", killed or "无")
    _ = Path, sys


if __name__ == "__main__":
    main()

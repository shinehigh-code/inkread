"""打包单文件 exe（Windows）。

用法：
    <venv>/Scripts/python.exe build.py
产物：
    dist/墨读.exe
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "墨读"


def main() -> int:
    icon = ROOT / "assets" / "icon.ico"
    if not icon.exists():
        try:
            subprocess.run([sys.executable, str(ROOT / "tools" / "make_icon.py")], check=True)
        except Exception as e:
            print("图标生成失败（继续打包）：", e)

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",
        "--windowed",
        "--name", NAME,
        "--add-data", f"{ROOT / 'web'}{os.pathsep}web",
        "--additional-hooks-dir", str(ROOT / "tools" / "hooks"),
        "--collect-data", "opencc",               # 仅词典数据，不重复收集源码与元数据
        "--hidden-import", "markdown.extensions.extra",
        "--hidden-import", "markdown.extensions.sane_lists",
        "--hidden-import", "markdown.extensions.toc",
        "--hidden-import", "webview.platforms.edgechromium",
        "--hidden-import", "webview.platforms.winforms",
        "--optimize", "1",
        # Windows x64/WebView2 不需要这些可选后端和图片科学计算栈。
        "--exclude-module", "numpy",
        "--exclude-module", "PIL",
        "--exclude-module", "tkinter",
        "--exclude-module", "webview.platforms.android",
        "--exclude-module", "webview.platforms.cef",
        "--exclude-module", "webview.platforms.cocoa",
        "--exclude-module", "webview.platforms.gtk",
        "--exclude-module", "webview.platforms.mshtml",
        "--exclude-module", "webview.platforms.qt",
    ]
    if icon.exists():
        args += ["--icon", str(icon)]
    args.append(str(ROOT / "main.py"))

    print(" ".join(args[:8]), "...")
    return subprocess.run(args, cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())

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
        "--collect-all", "webview",           # WebView2 程序集与加载器
        "--collect-all", "opencc",            # 繁简词典
        "--collect-submodules", "markdown",
        "--hidden-import", "webview.platforms.edgechromium",
        "--hidden-import", "webview.platforms.winforms",
    ]
    if icon.exists():
        args += ["--icon", str(icon)]
    args.append(str(ROOT / "main.py"))

    print(" ".join(args[:8]), "...")
    return subprocess.run(args, cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())

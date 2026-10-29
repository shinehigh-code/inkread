"""PyInstaller hook：Windows x64 仅打包 InkRead 实际使用的 pywebview 资源。"""
from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, get_package_paths

_, package_dir = get_package_paths("webview")
root = Path(package_dir)

datas = collect_data_files("webview", subdir="js")
binaries = [
    (str(root / "lib" / "Microsoft.Web.WebView2.Core.dll"), "webview/lib"),
    (str(root / "lib" / "Microsoft.Web.WebView2.WinForms.dll"), "webview/lib"),
]
# pywebview 6.2 初始化时会依次解析这三个目录；即便当前机器只使用 x64，
# 缺任意一个目录也会在导入阶段抛 FileNotFoundError，因此保留三个小型加载器。
for platform in ("win-arm64", "win-x64", "win-x86"):
    binaries.append(
        (
            str(root / "lib" / "runtimes" / platform / "native" / "WebView2Loader.dll"),
            f"webview/lib/runtimes/{platform}/native",
        )
    )

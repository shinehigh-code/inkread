"""入口：启动本地服务 + pywebview 窗口。"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main():
    from app import config
    from app.api import JsApi
    from app.log import install_hooks, log
    from app.server import serve

    # 传给 WebView2 的额外启动参数：关闭窗口遮挡检测，
    # 否则窗口被完全遮住或最小化时页面会被判定为隐藏，朗读与滚动跟随可能被节流。
    os.environ.setdefault(
        "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
        "--disable-features=CalculateNativeWinOcclusion",
    )

    install_hooks()
    log(f"启动 {config.APP_NAME} v{config.VERSION}（frozen={getattr(sys, 'frozen', False)}）")

    httpd, port = serve()
    log(f"本地服务已监听 127.0.0.1:{port}，数据目录 {config.data_dir()}")

    debug = bool(os.environ.get("INKREAD_DEBUG"))
    if debug:
        try:
            (Path(os.environ.get("TEMP", ".")) / "inkread-port.txt").write_text(str(port), "utf-8")
        except Exception:
            pass

    import webview

    gui = os.environ.get("INKREAD_GUI") or None
    if os.environ.get("INKREAD_DIAG"):
        from app.diag import start as start_diag

        start_diag()
    win_cfg = httpd.ctx.settings.get("window") or {}

    # 只允许标题栏/阅读器工具栏拖动窗口：pywebview 的 easy_drag 会让整窗任意位置都能拖动，
    # 那会连带把「选中文字」变成拖窗口。这里关掉 easy_drag（见 create_window），
    # 并用 DRAG_REGION_SELECTOR 精确限定可拖区域。
    webview.settings["DRAG_REGION_SELECTOR"] = ".titlebar, .r-bar"
    webview.settings["DRAG_REGION_DIRECT_TARGET_ONLY"] = False

    api = JsApi()

    # 安全护栏：pywebview 会递归展开 js_api 的所有公开非函数属性
    # （见 webview/util.py 的 get_functions），一旦持有可能递归的对象就会卡死窗口。
    bad_attrs = [n for n in dir(api) if not n.startswith("_") and not callable(getattr(api, n, None))]
    if bad_attrs:
        log(f"警告：JsApi 存在公开的非函数属性，可能导致卡死：{bad_attrs}")

    window = webview.create_window(
        f"{config.APP_NAME} · 本地阅读器",
        f"http://127.0.0.1:{port}",
        js_api=api,
        frameless=True,
        easy_drag=False,
        width=int(win_cfg.get("w", 1180)),
        height=int(win_cfg.get("h", 780)),
        min_size=(960, 600),
    )
    # 记到模块级（不是 JsApi 属性），供原生对话框使用
    from app import api as api_module

    api_module.set_window(window)

    def _save_window_state():
        try:
            state = str(getattr(window, "state", "") or "").lower()
            if "maxim" not in state and "fullscreen" not in state:
                httpd.ctx.settings["window"] = {"w": int(window.width), "h": int(window.height)}
                httpd.ctx.save_settings()
            log("窗口已关闭，尺寸已保存")
        except Exception as e:
            log(f"保存窗口尺寸失败：{e}")

    window.events.closing += _save_window_state
    log(f"开始创建窗口（后端 {gui or '自动'}）")
    webview.start(debug=debug, gui=gui)
    log("已退出")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        from app.log import log

        log("启动失败：\n" + traceback.format_exc())
        sys.exit(1)

"""入口：启动本地服务 + pywebview 窗口。"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _cli_paths() -> list[str]:
    """收集命令行里的文件 / 文件夹路径。

    Windows 资源管理器的「打开方式」把文件路径作为第一个参数传进来。
    早先完全没读 sys.argv，所以选「用墨读打开」只会落到书库首页。
    """
    from app.log import log

    out: list[str] = []
    for raw in sys.argv[1:]:
        arg = raw.strip().strip('"').strip("'")
        if not arg or arg.startswith("-"):
            continue
        try:
            p = Path(arg).expanduser()
        except OSError:
            continue
        if not p.exists():
            log(f"命令行参数不是有效路径，已忽略：{arg}")
            continue
        s = str(p.resolve())
        if s not in out:
            out.append(s)
    return out


def _instance_file() -> Path:
    from app import config

    return config.data_dir() / "instance.json"


def _try_handoff(paths: list[str]) -> bool:
    """若已有窗口在运行，就把路径交给它打开并返回 True（本进程随后退出）。

    不转交的话会开出第二个窗口，两个进程同时写 library.json 有互相覆盖的风险。
    """
    import json
    import urllib.request

    from app.log import log

    f = _instance_file()
    if not f.is_file():
        return False
    try:
        info = json.loads(f.read_text("utf-8"))
        port = int(info["port"])
        pid = int(info.get("pid") or 0)
    except Exception:
        return False
    if pid == os.getpid():
        return False

    # 只连本机回环，必须绕开系统代理
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/api/ping", timeout=1.5) as r:
            if r.status != 200:
                log(f"已有窗口探测返回 {r.status}，改为自行启动")
                return False
    except Exception as e:
        log(f"探测已有窗口失败（{type(e).__name__}: {e}），改为自行启动")
        return False  # 上一个实例已经退出，实例文件是残留
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/open-file",
            data=json.dumps({"paths": paths}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with opener.open(req, timeout=8) as r:
            res = json.loads(r.read().decode("utf-8"))
        log(f"已有窗口在运行（端口 {port}），已把文件转交给它打开：{res.get('id')}")
        return True
    except Exception as e:
        log(f"转交运行中的窗口失败，改为自行启动：{e}")
        return False


def _write_instance(port: int) -> None:
    import json
    import time

    from app.log import log

    try:
        _instance_file().write_text(
            json.dumps({"pid": os.getpid(), "port": port, "ts": time.time()}), "utf-8"
        )
    except Exception as e:
        log(f"写入实例信息失败：{e}")


def _clear_instance() -> None:
    """退出时删掉实例文件，但只删属于本进程的那份。"""
    import json

    try:
        f = _instance_file()
        if f.is_file():
            info = json.loads(f.read_text("utf-8"))
            if int(info.get("pid") or 0) == os.getpid():
                f.unlink()
    except Exception:
        pass


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

    # 「用墨读打开」传来的文件：已有窗口就直接交给它，本进程退出
    startup = _cli_paths()
    if startup and _try_handoff(startup):
        log("文件已交给运行中的窗口，本次启动结束")
        return

    httpd, port = serve()
    _write_instance(port)
    log(f"本地服务已监听 127.0.0.1:{port}，数据目录 {config.data_dir()}")

    # 启动参数里的文件先入库，再让窗口直接进阅读器（而不是停在书库首页）
    open_id = ""
    if startup:
        try:
            res = httpd.ctx.lib.add(startup)
            if res["added"]:
                first = res["added"][0]
                open_id = first["id"]
                log(f"命令行打开《{first.get('title', '')}》→ {open_id}")
            for err in res["errors"]:
                log(f"命令行文件无法打开：{err.get('path')}：{err.get('error')}")
        except Exception as e:
            log(f"处理命令行文件失败：{e}")
    start_url = f"http://127.0.0.1:{port}" + (f"#/read/{open_id}" if open_id else "")

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
        start_url,
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

    def _navigate(bid: str):
        """运行中收到新文件时，把窗口提到最前并跳到对应书籍。"""
        import json as _json

        from app import win32

        try:
            win32.bring_to_front()
        except Exception as e:
            log(f"置顶窗口失败：{e}")
        try:
            window.evaluate_js(f"window.__inkreadOpen && window.__inkreadOpen({_json.dumps(bid)})")
        except Exception as e:
            log(f"通知前端打开书籍失败：{e}")

    httpd.ctx.navigate = _navigate

    if open_id:
        # 从资源管理器「用墨读打开」时，确保窗口出现在最前面，别被别的程序盖住
        import threading
        import time as _time

        from app import win32 as _win32

        def _front():
            _time.sleep(1.2)
            try:
                _win32.bring_to_front()
            except Exception:
                pass

        threading.Thread(target=_front, daemon=True).start()

    def _save_window_state():
        try:
            state = str(getattr(window, "state", "") or "").lower()
            if "maxim" not in state and "fullscreen" not in state:
                httpd.ctx.settings["window"] = {"w": int(window.width), "h": int(window.height)}
                httpd.ctx.save_settings()
            log("窗口已关闭，尺寸已保存")
        except Exception as e:
            log(f"保存窗口尺寸失败：{e}")
        _clear_instance()

    window.events.closing += _save_window_state
    log(f"开始创建窗口（后端 {gui or '自动'}）")
    webview.start(debug=debug, gui=gui)
    _clear_instance()
    log("已退出")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        from app.log import log

        log("启动失败：\n" + traceback.format_exc())
        sys.exit(1)

"""验证「用墨读打开」这条链路（回归测试）。

覆盖三件事：
  1. 带文件参数启动，窗口直接进阅读器（而不是停在书库首页）
  2. 窗口已开着时再打开另一个文件，第二个进程把文件转交后立即退出
  3. 原窗口真的切到了新书

判定方式：读应用日志里的「命令行打开」与「DOM 探测」（自检用 evaluate_js 取
location.hash 与阅读器状态），不依赖截图，避免被别的窗口遮挡干扰。

用法：
    python samples/test_cli_open.py          # 测源码模式
    python samples/test_cli_open.py --exe    # 测打包后的 dist/墨读.exe
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / ".clitest"
LOG = DATA / "inkread.log"
USE_EXE = "--exe" in sys.argv

passed, failed = [], []


def check(name: str, cond: bool, detail: str = ""):
    (passed if cond else failed).append(name)
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  | {detail}"), flush=True)


def read_log() -> str:
    try:
        return LOG.read_text("utf-8", errors="ignore")
    except OSError:
        return ""


def wait_for(pred, timeout: float, interval: float = 0.5):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = pred()
        if v:
            return v
        time.sleep(interval)
    return None


def ping(port: int) -> bool:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/api/ping", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def launch(book: Path):
    env = dict(os.environ)
    env.update({"INKREAD_HOME": str(DATA), "INKREAD_DIAG": "1"})
    if USE_EXE:
        cmd = [str(ROOT / "dist" / "墨读.exe"), str(book)]
    else:
        cmd = [sys.executable, str(ROOT / "main.py"), str(book)]
    return subprocess.Popen(cmd, cwd=str(ROOT), env=env,
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def kill_tree(proc):
    try:
        import psutil

        for child in psutil.Process(proc.pid).children(recursive=True):
            try:
                child.kill()
            except Exception:
                pass
        proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def main() -> int:
    if USE_EXE and not (ROOT / "dist" / "墨读.exe").is_file():
        print("找不到 dist/墨读.exe，请先运行 python build.py")
        return 2
    if DATA.exists():
        shutil.rmtree(DATA)
    book1 = ROOT / "samples" / "novel_gbk.txt"
    book2 = ROOT / "samples" / "notes.md"
    for b in (book1, book2):
        if not b.is_file():
            print(f"缺少样本 {b}，先运行 python samples/make_samples.py")
            return 2

    mode = "打包版" if USE_EXE else "源码模式"
    print(f"=== 测试「用墨读打开」（{mode}）===", flush=True)

    # ---- 1. 带文件启动
    a = launch(book1)
    try:
        inst = wait_for(lambda: (DATA / "instance.json").is_file()
                        and json.loads((DATA / "instance.json").read_text("utf-8")), 40)
        check("应用启动并登记实例", bool(inst), "40 秒内没写出 instance.json")
        if not inst:
            return 1
        port = int(inst["port"])
        check("本地服务可访问", bool(wait_for(lambda: ping(port), 20)))

        opened = wait_for(lambda: "命令行打开" in read_log(), 25)
        check("识别到命令行传入的文件", bool(opened))
        rid = None
        for line in read_log().splitlines():
            if "命令行打开" in line and "→" in line:
                rid = line.rsplit("→", 1)[1].strip()

        # 前端真的进了阅读器（DOM 探测里有该书的 hash）
        def dom_has(bid: str):
            for line in read_log().splitlines():
                if "DOM 探测" in line and f"#/read/{bid}" in line and "'reader': True" in line:
                    return line
            return None

        hit = wait_for(lambda: dom_has(rid), 45) if rid else None
        check("窗口直接进入阅读器", bool(hit), f"没等到 #/read/{rid} 的 DOM 探测")

        # ---- 2. 已开着时再打开另一个文件
        t0 = time.time()
        b = launch(book2)
        try:
            code = b.wait(timeout=30)
            second_exited = True
        except subprocess.TimeoutExpired:
            code, second_exited = None, False
            kill_tree(b)
        cost = time.time() - t0
        check("第二个进程自动退出（转交给已有窗口）", second_exited and code == 0,
              f"退出码={code} 耗时={cost:.1f}s")

        ids = [ln for ln in read_log().splitlines() if "已把文件转交给它打开" in ln]
        check("日志记录了转交目标", bool(ids), str(ids[-1:]))

        # ---- 3. 原窗口切到了新书
        target = None
        for ln in ids:
            seg = ln.rsplit("：", 1)[-1].strip()
            if len(seg) == 12:
                target = seg
        switched = wait_for(lambda: dom_has(target), 45) if target else None
        check("原窗口切换到新书", bool(switched), f"没等到 #/read/{target} 的 DOM 探测")
        if switched:
            print("      探测到:", switched.split("DOM 探测：", 1)[-1][:110])
    finally:
        kill_tree(a)

    print(f"\n===== {len(passed)} 通过, {len(failed)} 失败 =====")
    if failed:
        print("失败项：", failed)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

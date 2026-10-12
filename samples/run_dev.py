"""开发模式：启动服务并自动导入样本书籍，端口打印到 stdout。"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("INKREAD_HOME", str(ROOT / ".devdata"))
sys.path.insert(0, str(ROOT))

from app.server import serve  # noqa: E402

httpd, port = serve()

samples = ROOT / "samples"
paths = []
for p in sorted(samples.iterdir()):
    if p.suffix.lower() in (".txt", ".md", ".epub", ".cbz", ".7z"):
        paths.append(str(p))
    elif p.is_dir() and p.name.startswith("comic"):
        paths.append(str(p))
res = httpd.ctx.lib.add(paths)
print("PORT", port, flush=True)
print("ADDED", len(res["added"]), "ERRORS", res["errors"], flush=True)

try:
    while True:
        time.sleep(3600)
except KeyboardInterrupt:
    httpd.shutdown()

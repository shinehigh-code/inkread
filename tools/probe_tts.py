"""探测 WebView2 的语音合成能力。

页面用 no-cors POST 把结果回传到本脚本起的临时 HTTP 端口（pywebview 的
document.title 不会回传到窗口标题，所以另开通道）。

用法：python tools/probe_tts.py
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import webview

PORT = 8791
results: list[str] = []

HTML = """<!doctype html><meta charset="utf-8"><body style="font:13px sans-serif;padding:14px;white-space:pre-wrap">
<div id="out">探测中…</div>
<script>
const PORT = %(port)d;
function send(tag, data){
  const body = tag + ' ' + (typeof data === 'string' ? data : JSON.stringify(data));
  document.getElementById('out').textContent += '\\n' + body;
  try { fetch('http://127.0.0.1:' + PORT + '/report', {method:'POST', mode:'no-cors', body: body}); } catch(e) {}
}
function dump(){
  const vs = speechSynthesis.getVoices();
  send('COUNT', vs.length);
  vs.forEach(function(v, i){
    send('VOICE', i + '|' + v.name + '|' + v.lang + '|' + (v.localService ? 'local' : 'online') + '|' + (v.default ? 'default' : ''));
  });
  return vs;
}
if (!('speechSynthesis' in window)) { send('NOSUPPORT', 'speechSynthesis missing'); }
else {
  let vs = dump();
  speechSynthesis.onvoiceschanged = function(){ vs = dump(); };
  setTimeout(function(){
    if (!vs.length) vs = dump();
    if (!vs.length) { send('EMPTY', 'no voices'); return; }
    const zh = vs.filter(function(v){ return /zh|Chinese|Huihui|Xiaoxiao|Kangkang|Yaoyao|Yunxi|Xiaoyi/i.test(v.name + ' ' + v.lang); });
    send('ZH', zh.length);
    const pick = zh[0] || vs[0];
    send('PICK', pick.name);
    const u = new SpeechSynthesisUtterance('墨读语音测试，一二三四五。');
    u.voice = pick; u.lang = pick.lang || 'zh-CN'; u.rate = 1.0;
    u.onstart = function(){ send('EVENT', 'start'); };
    u.onend = function(){ send('EVENT', 'end'); };
    u.onerror = function(e){ send('EVENT', 'error:' + (e.error || '?')); };
    u.onboundary = function(e){ send('BOUNDARY', (e.name || '?') + '@' + e.charIndex); };
    speechSynthesis.speak(u);
    setTimeout(function(){ send('STATE', 'speaking=' + speechSynthesis.speaking + ' pending=' + speechSynthesis.pending); }, 1200);
  }, 1500);
}
</script></body>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode("utf-8", "replace")
        results.append(body)
        print("[收到]", body[:400], flush=True)
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", "0")
        self.end_headers()


def main():
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    html = HTML % {"port": PORT}
    w = webview.create_window("TTS 探测", html=html, width=780, height=460,
                              easy_drag=False)

    def finish():
        time.sleep(14)
        try:
            w.destroy()
        except Exception:
            pass

    w.events.loaded += lambda: threading.Thread(target=finish, daemon=True).start()
    webview.start()
    httpd.shutdown()
    print("\n=== 汇总 ===")
    print(f"共收到 {len(results)} 条回传")


if __name__ == "__main__":
    main()

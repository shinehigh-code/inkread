// 语音朗读：使用 WebView2 内置的 speechSynthesis（走系统语音，离线可用）
// 逐句朗读 + 跟随高亮 + 自动滚动/翻页，读完本章可自动续读下一章。

const VOICE_CN = {
  huihui: ['慧慧', '女'],
  kangkang: ['康康', '男'],
  yaoyao: ['瑶瑶', '女'],
  xiaoxiao: ['晓晓', '女'],
  xiaoyi: ['晓伊', '女'],
  yunxi: ['云希', '男'],
  yunjian: ['云健', '男'],
  yunyang: ['云扬', '男'],
  yunxia: ['云夏', '女'],
  zhiwei: ['志伟', '男'],
};

export function ttsSupported() {
  return typeof window.speechSynthesis !== 'undefined' && typeof window.SpeechSynthesisUtterance !== 'undefined';
}

function describe(v) {
  const base = (v.name.split(' - ')[0] || '').replace(/^Microsoft\s+/i, '').trim();
  const info = VOICE_CN[base.toLowerCase()];
  const zh = /^zh/i.test(v.lang || '') || !!info;
  let label = info ? `${info[0]}（${info[1]}` : base;
  if (info) label += v.localService === false ? '·在线）' : '·本地）';
  else label += `（${v.lang || '未知'}${v.localService === false ? '·在线' : ''}）`;
  return { id: v.name, label, zh, local: v.localService !== false, lang: v.lang || '' };
}

let _voices = [];

export function listVoices() {
  if (!ttsSupported()) return [];
  const raw = window.speechSynthesis.getVoices() || [];
  _voices = raw
    .filter((v) => /^zh/i.test(v.lang || '') || VOICE_CN[(v.name.split(' - ')[0] || '').replace(/^Microsoft\s+/i, '').trim().toLowerCase()])
    .map(describe);
  if (!_voices.length) _voices = raw.map(describe); // 没有中文语音时也列出来
  _voices.sort((a, b) => (b.zh - a.zh) || (b.local - a.local) || a.label.localeCompare(b.label));
  return _voices;
}

export function onVoicesReady(cb) {
  if (!ttsSupported()) return;
  const fire = () => cb(listVoices());
  fire();
  window.speechSynthesis.addEventListener('voiceschanged', fire);
}

const SENT_SPLIT = /(?<=[。！？!?；;…]+[”"』」）)]*)/;
const SENT_HAS = /[。！？!?；;…]/;
const BLOCK_SEL = 'p, li, h1, h2, h3, h4, h5, h6, .ch-head .ch-title';

export class Speaker {
  constructor(reader) {
    this.r = reader;
    this.active = false;
    this.paused = false;
    this.units = [];       // [{el, text}] 朗读单元（句子级）
    this.idx = 0;
    this.done = false;
    this._token = 0;
  }

  cfg() {
    const t = (this.r.s && this.r.s.tts) || {};
    return {
      voice: t.voice || '',
      rate: t.rate == null ? 1 : t.rate,
      pitch: t.pitch == null ? 1 : t.pitch,
      volume: t.volume == null ? 1 : t.volume,
    };
  }

  // ---------- 单元切分：把段落按句切开并包 <span class="tts-s">
  prepare() {
    const flow = this.r.$flow;
    flow.querySelectorAll('.tts-s').forEach((s) => s.replaceWith(document.createTextNode(s.textContent)));
    const blocks = [...flow.querySelectorAll(BLOCK_SEL)]
      .filter((el) => !el.closest('pre') && (el.textContent || '').trim().length > 0);
    const units = [];
    for (const el of blocks) {
      this._split(el);
      const spans = [...el.querySelectorAll('.tts-s')];
      if (spans.length) {
        spans.forEach((s) => {
          const t = (s.textContent || '').trim();
          if (t) units.push({ el: s, text: t });
        });
      } else {
        units.push({ el, text: (el.textContent || '').trim() });
      }
    }
    this.units = units;
    return units;
  }

  _split(el) {
    if (el.dataset.ttsSplit) return;
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const n of nodes) {
      const text = n.nodeValue || '';
      if (!text.trim() || !SENT_HAS.test(text)) continue;
      const parts = text.split(SENT_SPLIT).filter((s) => s !== '');
      if (parts.length < 2) continue;
      const frag = document.createDocumentFragment();
      for (const p of parts) {
        if (!p.trim()) {
          frag.appendChild(document.createTextNode(p));
          continue;
        }
        const s = document.createElement('span');
        s.className = 'tts-s';
        s.textContent = p;
        frag.appendChild(s);
      }
      n.replaceWith(frag);
    }
    el.dataset.ttsSplit = '1';
  }

  cleanup() {
    const flow = this.r.$flow;
    flow.querySelectorAll('.tts-on').forEach((s) => s.classList.remove('tts-on'));
    flow.querySelectorAll('.tts-s').forEach((s) => s.replaceWith(document.createTextNode(s.textContent)));
    flow.querySelectorAll('[data-tts-split]').forEach((el) => delete el.dataset.ttsSplit);
    flow.normalize();
    this.units = [];
  }

  // ---------- 播放控制
  startFromVisible() {
    try {
      if (!ttsSupported()) {
        this.r.notify('当前环境不支持语音朗读');
        return;
      }
      this.prepare();
      if (!this.units.length) {
        this.r.notify('这一章没有可朗读的文字');
        return;
      }
      const pv = this.r.$pv.getBoundingClientRect();
      let start = 0;
      for (let i = 0; i < this.units.length; i++) {
        const r = this.units[i].el.getBoundingClientRect();
        if (r.bottom > pv.top + 8) {
          start = i;
          break;
        }
      }
      this.play(start);
    } catch (e) {
      this.r.notify('朗读启动失败：' + (e && e.message ? e.message : e));
      this.stop('start-error');
    }
  }

  play(index) {
    if (!this.units.length) return;
    window.speechSynthesis.cancel();          // 清掉引擎里排队的旧内容
    this.idx = Math.max(0, Math.min(this.units.length - 1, index));
    this.active = true;
    this.paused = false;
    this.done = false;
    this._token += 1;
    this.r.onSpeakState();
    this._speak(this.idx, this._token);
  }

  _speak(i, token) {
    if (!this.active || token !== this._token) return;
    if (i >= this.units.length) {
      this.done = true;
      if (!this.r.speakNextChapter()) this.stop('book-end');
      return;
    }
    this.idx = i;
    const unit = this.units[i];
    this._highlight(unit.el);
    this.r.followSpeak(unit.el);

    const cfg = this.cfg();
    const u = new SpeechSynthesisUtterance(unit.text);
    const v = (window.speechSynthesis.getVoices() || []).find((x) => x.name === cfg.voice);
    if (v) {
      u.voice = v;
      u.lang = v.lang;
    } else {
      u.lang = 'zh-CN';
    }
    u.rate = cfg.rate;
    u.pitch = cfg.pitch;
    u.volume = cfg.volume;
    u.onend = () => {
      if (!this.active || token !== this._token) return;
      this._speak(i + 1, token);
    };
    u.onerror = (e) => {
      if (!this.active || token !== this._token) return;
      const err = String(e.error || '').toLowerCase();
      if (err === 'interrupted' || err === 'canceled' || err === 'cancelled') return;
      // 音频子系统尚未就绪、引擎忙等偶发情况：同一句重试一次
      if (err === 'not-allowed' || err === 'audio-busy' || err === 'synthesis-failed' || !err) {
        if (this._retriedAt !== i) {
          this._retriedAt = i;
          setTimeout(() => {
            if (this.active && token === this._token) this._speak(i, token);
          }, 600);
          return;
        }
        this.r.notify('朗读被系统拒绝，请稍后再点一次喇叭图标');
        this.stop('rejected');
        return;
      }
      // 其它偶发错误：跳过这一句继续往下读，不要整段中止
      this.r.notify('跳过一句（' + (e.error || '朗读错误') + '）');
      this._speak(i + 1, token);
    };
    this.utterance = u;
    try {
      window.speechSynthesis.speak(u);
    } catch (e) {
      this.r.notify('朗读启动失败：' + (e && e.message ? e.message : e));
      this.stop('speak-throw');
      return;
    }
    this.r.updateSpeakUI(this.idx + 1, this.units.length);
  }

  _highlight(el) {
    const flow = this.r.$flow;
    flow.querySelectorAll('.tts-on').forEach((s) => s.classList.remove('tts-on'));
    if (el && el.classList) el.classList.add('tts-on'); // 分句后的 span 或整段
  }

  pause() {
    if (!this.active || this.paused) return;
    this.paused = true;
    try {
      window.speechSynthesis.pause();
    } catch (e) { /* 忽略 */ }
    // 部分引擎 pause 无效，兜底用 cancel + 记住位置
    setTimeout(() => {
      if (this.paused && this.active && !window.speechSynthesis.speaking) {
        this._resumeFallback = true;
      }
    }, 350);
    this.r.onSpeakState();
  }

  resume() {
    if (!this.active || !this.paused) return;
    this.paused = false;
    if (this._resumeFallback) {
      this._resumeFallback = false;
      this._token += 1;
      this._speak(this.idx, this._token);
      return;
    }
    try {
      window.speechSynthesis.resume();
    } catch (e) { /* 忽略 */ }
    setTimeout(() => {
      if (this.active && !this.paused && !window.speechSynthesis.speaking) {
        this._token += 1;
        this._speak(this.idx, this._token);
      }
    }, 600);
    this.r.onSpeakState();
  }

  next() {
    if (!this.active) return;
    this._token += 1;
    this.play(this.idx + 1);
  }

  prev() {
    if (!this.active) return;
    this._token += 1;
    this.play(this.idx - 1);
  }

  stop(reason) {
    this.active = false;
    this.paused = false;
    this._token += 1;
    if (reason && this.r.el) this.r.el.dataset.ttsStop = reason; // 排查用：记录停止原因
    try {
      window.speechSynthesis.cancel();
    } catch (e) { /* 忽略 */ }
    this.cleanup();
    this.r.onSpeakState();
    this.r.updateSpeakUI(0, 0);
  }

  /** 切章后继续朗读（由阅读器在章节加载完成后调用）。 */
  continueAfterChapter() {
    if (!this.active) return false;
    this.prepare();
    if (!this.units.length) {
      this.stop();
      return false;
    }
    this.play(0);
    return true;
  }
}

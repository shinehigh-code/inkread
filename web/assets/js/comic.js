// 漫画阅读器：CBZ / CBR / CB7 / CBT / 图片文件夹
import { api, bridge } from './api.js';
import { icon, esc, debounce, patchSettings } from './ui.js';

const FIT_MODES = [
  { key: 'fit-height', icon: 'fith', name: '适应高度' },
  { key: 'fit-width', icon: 'fitw', name: '适应宽度' },
  { key: 'original', icon: 'original', name: '原始大小' },
  { key: 'continuous', icon: 'scroll', name: '连续滚动' },
];

export class ComicReader {
  constructor(app, info) {
    this.app = app;
    this.meta = info.meta;
    this.total = info.meta.pages || 0;
    this.s = app.state.settings;
    this.fit = this.s.comic?.fit || 'fit-height';
    this.spread = this.s.comic?.spread || 'single';
    this.dir = this.s.comic?.dir || 'ltr';
    this.page = Math.min(info.progress?.page || 0, Math.max(0, this.total - 1));
    this._save = debounce(() => this._saveNow(), 600);
    this._onScroll = debounce(() => this.trackContinuous(), 140);
    this.io = null;
  }

  $(sel) { return this.el.querySelector(sel); }

  mount() {
    document.body.insertAdjacentHTML('beforeend', this.template());
    this.el = document.getElementById('reader');
    this.$stage = this.$('#stage');
    this.$stage.addEventListener('scroll', this._onScroll);

    // 滚轮翻页（连续滚动模式交给系统滚动）
    this._wacc = 0;
    this._wlock = 0;
    this._onWheel = (e) => {
      if (this.fit === 'continuous' || e.ctrlKey) return;
      e.preventDefault();
      const now = Date.now();
      if (now < this._wlock) return;
      this._wacc += e.deltaY;
      if (Math.abs(this._wacc) < 24) return;
      const dir = this._wacc > 0 ? 1 : -1;
      this._wacc = 0;
      this._wlock = now + 220;
      if (dir > 0) this.next();
      else this.prev();
    };
    this.$stage.addEventListener('wheel', this._onWheel, { passive: false });

    this.render();
    const hint = this.$('#hint');
    hint.classList.add('show');
    setTimeout(() => hint.classList.remove('show'), 2000);
  }

  template() {
    const fitMode = FIT_MODES.find((m) => m.key === this.fit) || FIT_MODES[0];
    return `
  <div class="reader" id="reader">
    <div class="r-bar">
      <button class="icon-btn" data-act="back" title="返回书架 (Esc)">${icon('back', 17)}</button>
      <div class="r-title" id="rtitle"></div>
      <button class="icon-btn" data-act="fullscreen" title="全屏 (F11)">${icon('fullscreen', 16)}</button>
    </div>
    <div class="comic-stage" id="stage">
      <div class="comic-wrap" id="wrap"></div>
      <div class="comic-loading" id="loading" style="display:none"><div class="spin"></div></div>
      <button class="zone l" data-act="prev" tabindex="-1" aria-label="上一页"></button>
      <button class="zone r" data-act="next" tabindex="-1" aria-label="下一页"></button>
      <div class="comic-nav-hint" id="hint"></div>
    </div>
    <div class="r-bar btm">
      <button class="icon-btn pg-btn" data-act="prev" title="上一页">${icon('chev-l', 15)}</button>
      <input type="range" id="pgsld" min="0" max="${Math.max(0, this.total - 1)}" value="${this.page}" title="页码">
      <div class="page-label" id="pglabel"></div>
      <button class="icon-btn pg-btn" data-act="next" title="下一页">${icon('chev-r', 15)}</button>
      <div class="r-sep"></div>
      <button class="icon-btn cm-btn" data-act="fit" title="缩放模式：${fitMode.name}">${icon(fitMode.icon, 16)}</button>
      <button class="icon-btn cm-btn" data-act="spread" title="单页 / 双页">${icon(this.spread === 'double' ? 'double' : 'single', 16)}</button>
      <button class="icon-btn cm-btn" data-act="dir" title="阅读方向">${icon(this.dir === 'rtl' ? 'arrow-l' : 'arrow-r', 16)}</button>
    </div>
  </div>`;
  }

  destroy() {
    if (this.io) this.io.disconnect();
    this.$stage?.removeEventListener('scroll', this._onScroll);
    if (this._onWheel) this.$stage?.removeEventListener('wheel', this._onWheel);
    this._saveNow();
    if (this.el) this.el.remove();
  }

  // ---------------------------------------------------------------- 渲染

  render() {
    this.$stage.className = 'comic-stage ' + (this.fit === 'continuous' ? 'continuous' : this.fit);
    if (this.fit === 'continuous') this.renderContinuous();
    else this.renderPaged();
    this.updateChrome();
  }

  spreadIdx() {
    if (this.spread === 'single') return [this.page];
    if (this.page === 0) return [0];
    const base = 1 + 2 * Math.floor((this.page - 1) / 2);
    const out = [base];
    if (base + 1 < this.total) out.push(base + 1);
    return out;
  }

  renderPaged() {
    if (this.io) { this.io.disconnect(); this.io = null; }
    const idxs = this.spreadIdx();
    const imgs = idxs.map((i) =>
      `<img class="cpage contain" src="${api.page(this.meta.id, i)}" alt="第 ${i + 1} 页">`);
    this.$('#wrap').innerHTML = (this.dir === 'rtl' ? imgs.reverse() : imgs).join('');
    for (const off of [1, 2, -1, -2]) {
      const i = this.page + off;
      if (i >= 0 && i < this.total) {
        const im = new Image();
        im.src = api.page(this.meta.id, i);
      }
    }
  }

  renderContinuous() {
    const wrap = this.$('#wrap');
    wrap.innerHTML = Array.from({ length: this.total }, (_, i) =>
      `<img class="cpage" data-src="${api.page(this.meta.id, i)}" data-i="${i}" alt="第 ${i + 1} 页">`).join('');
    this.io = new IntersectionObserver((entries) => {
      for (const en of entries) {
        if (!en.isIntersecting) continue;
        const img = en.target;
        if (img.dataset.src) {
          img.src = img.dataset.src;
          delete img.dataset.src;
        }
      }
    }, { root: this.$stage, rootMargin: '400px 0px' });
    wrap.querySelectorAll('img').forEach((img) => this.io.observe(img));
    requestAnimationFrame(() => this.scrollToPage(this.page));
  }

  scrollToPage(n) {
    const img = this.$('#wrap').querySelector(`img[data-i="${n}"]`);
    if (img) img.scrollIntoView({ block: 'start' });
  }

  trackContinuous() {
    const imgs = this.$('#wrap').querySelectorAll('img');
    const line = this.$stage.scrollTop + this.$stage.clientHeight * 0.4;
    let cur = 0;
    imgs.forEach((img) => {
      if (img.offsetTop <= line) cur = Number(img.dataset.i);
    });
    if (cur !== this.page) {
      this.page = cur;
      this.updateChrome();
      this._save();
    }
  }

  // ---------------------------------------------------------------- 翻页

  step() { return this.spread === 'double' ? 2 : 1; }

  next() {
    if (this.fit === 'continuous') {
      this.$stage.scrollBy({ top: this.$stage.clientHeight * 0.9, behavior: 'smooth' });
      return;
    }
    const st = this.step();
    let n = this.page + st;
    if (this.spread === 'double' && this.page === 0) n = 1;
    this.go(Math.min(this.total - 1, n));
  }

  prev() {
    if (this.fit === 'continuous') {
      this.$stage.scrollBy({ top: -this.$stage.clientHeight * 0.9, behavior: 'smooth' });
      return;
    }
    const st = this.step();
    let n = this.page - st;
    if (this.spread === 'double' && n < 1) n = 0;
    this.go(Math.max(0, n));
  }

  go(n) {
    this.page = Math.max(0, Math.min(this.total - 1, n));
    if (this.fit === 'continuous') this.scrollToPage(this.page);
    else this.renderPaged();
    this.updateChrome();
    this._save();
  }

  // ---------------------------------------------------------------- 状态

  updateChrome() {
    const t = this.$('#rtitle');
    if (t) t.innerHTML = `<b>${esc(this.meta.title)}</b> <span style="color:var(--text-3)">·</span> ${esc(this.meta.fmt.toUpperCase())}`;
    const pl = this.$('#pglabel');
    if (pl) pl.textContent = `${this.page + 1} / ${this.total} 页`;
    const sl = this.$('#pgsld');
    if (sl && document.activeElement !== sl) sl.value = String(this.page);
  }

  _saveNow() {
    api.progress(this.meta.id, {
      chapter: 0,
      page: this.page,
      scroll: 0,
      pct: this.total > 1 ? this.page / (this.total - 1) : 1,
    }).catch(() => {});
  }

  // ---------------------------------------------------------------- 事件

  onAction(name, el) {
    switch (name) {
      case 'back': location.hash = '#/library'; break;
      case 'fullscreen': bridge('window_action', 'fullscreen').catch(() => {}); break;
      case 'prev': this.prev(); break;
      case 'next': this.next(); break;
      case 'fit': {
        const i = FIT_MODES.findIndex((m) => m.key === this.fit);
        const m = FIT_MODES[(i + 1) % FIT_MODES.length];
        this.fit = m.key;
        patchSettings({ comic: { ...this.s.comic, fit: m.key } });
        const btn = this.$('[data-act="fit"]');
        if (btn) {
          btn.innerHTML = icon(m.icon, 16);
          btn.title = '缩放模式：' + m.name;
        }
        this.render();
        break;
      }
      case 'spread': {
        this.spread = this.spread === 'double' ? 'single' : 'double';
        patchSettings({ comic: { ...this.s.comic, spread: this.spread } });
        const btn = this.$('[data-act="spread"]');
        if (btn) btn.innerHTML = icon(this.spread === 'double' ? 'double' : 'single', 16);
        this.render();
        break;
      }
      case 'dir': {
        this.dir = this.dir === 'rtl' ? 'ltr' : 'rtl';
        patchSettings({ comic: { ...this.s.comic, dir: this.dir } });
        const btn = this.$('[data-act="dir"]');
        if (btn) btn.innerHTML = icon(this.dir === 'rtl' ? 'arrow-l' : 'arrow-r', 16);
        this.render();
        break;
      }
      default: break;
    }
  }

  onChange(el) {
    if (el.id === 'pgsld') this.go(Number(el.value));
  }

  onKey(e) {
    if (e.target.matches('input, select, textarea')) return;
    const rtl = this.dir === 'rtl';
    switch (e.key) {
      case 'ArrowRight': e.preventDefault(); rtl ? this.prev() : this.next(); break;
      case 'ArrowLeft': e.preventDefault(); rtl ? this.next() : this.prev(); break;
      case 'PageDown': e.preventDefault(); this.next(); break;
      case 'PageUp': e.preventDefault(); this.prev(); break;
      case 'Home': e.preventDefault(); this.go(0); break;
      case 'End': e.preventDefault(); this.go(this.total - 1); break;
      case 'Escape': location.hash = '#/library'; break;
      case 'F11':
        e.preventDefault();
        bridge('window_action', 'fullscreen').catch(() => {});
        break;
      default: break;
    }
  }
}

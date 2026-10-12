// 文本阅读器：TXT / MD / EPUB
import { api, bridge } from './api.js';
import { icon, esc, toast, debounce, patchSettings, FONT_NAMES, CONVERT_NAMES } from './ui.js';
import { Speaker, ttsSupported, listVoices, onVoicesReady } from './tts.js';

const THEMES = ['paper', 'ink', 'sepia', 'moss', 'night'];

export class TextReader {
  constructor(app, info) {
    this.app = app;
    this.meta = info.meta;
    this.toc = info.toc || [];
    this.s = app.state.settings;
    this.progress = info.progress || {};
    this.bookmarks = info.bookmarks || [];
    this.ch = Math.min(this.progress.chapter || 0, Math.max(0, this.toc.length - 1));
    this.curPage = this.progress.page || 0;
    this.scrollRatio = this.progress.scroll || 0;
    this.total = Math.max(1, this.toc.length);
    this.pages = 1;
    this.step = 0;
    this.kw = '';
    this.popOpen = false;
    this.drawer = null;
    this.rightTab = 'bm';
    this.loading = false;
    this._save = debounce(() => this._saveNow(), 700);
    this._onResize = debounce(() => this.relayout(), 180);
  }

  $(sel) { return this.el.querySelector(sel); }

  // ---------------------------------------------------------------- 界面

  template() {
    return `
  <div class="reader" id="reader">
    <div class="r-bar">
      <button class="icon-btn" data-act="back" title="返回书架 (Esc)">${icon('back', 17)}</button>
      <div class="r-title" id="rtitle"></div>
      <button class="icon-btn" data-act="toc" title="目录">${icon('toc', 17)}</button>
      <select class="sel" id="cvt" style="height:28px;font-size:12px;width:84px" title="繁简转换">
        ${Object.entries(CONVERT_NAMES).map(([k, v]) => `<option value="${k}" ${this.s.convert === k ? 'selected' : ''}>${v}</option>`).join('')}
      </select>
      <button class="icon-btn" data-act="search" title="搜索 (Ctrl+F)">${icon('search', 17)}</button>
      <button class="icon-btn" data-act="bookmark" title="添加书签">${icon('bookmark', 17)}</button>
      <button class="icon-btn" data-act="tts" title="语音朗读">${icon('speaker', 17)}</button>
      <button class="icon-btn" data-act="font" title="阅读设置">${icon('type', 17)}</button>
      <button class="icon-btn" data-act="fullscreen" title="全屏 (F11)">${icon('fullscreen', 16)}</button>
    </div>

    <div class="stage" id="stage">
      <div class="page-view" id="pv"><div class="flow" id="flow"></div></div>
      <button class="zone l" data-act="prev" tabindex="-1" aria-label="上一页"></button>
      <button class="zone c" data-act="chrome" tabindex="-1" aria-label="显示或隐藏工具栏"></button>
      <button class="zone r" data-act="next" tabindex="-1" aria-label="下一页"></button>
      <div class="comic-loading" id="loading" style="display:none"><div class="spin"></div></div>
    </div>

    <div class="tts-bar" id="ttsbar" hidden>
      <button class="icon-btn" data-act="tts-toggle" title="暂停">${icon('pause', 15)}</button>
      <button class="icon-btn" data-act="tts-prev" title="上一句">${icon('chev-l', 15)}</button>
      <button class="icon-btn" data-act="tts-next" title="下一句">${icon('chev-r', 15)}</button>
      <div class="tts-info"><span class="tts-dot"></span><span id="ttsprog">正在朗读</span></div>
      <div class="r-spacer"></div>
      <button class="icon-btn" data-act="tts-stop" title="停止朗读">${icon('close', 15)}</button>
    </div>

    <div class="r-bar btm">
      <button class="icon-btn pg-btn" data-act="prev-ch" title="上一章">${icon('chev-l', 15)}</button>
      <div class="ch-name" id="chname"></div>
      <input type="range" id="pgsld" min="0" max="1000" value="0" title="阅读进度">
      <div class="page-label" id="pglabel"></div>
      <button class="icon-btn pg-btn" data-act="next-ch" title="下一章">${icon('chev-r', 15)}</button>
    </div>

    <div class="drawer left" id="toc-drawer">
      <div class="drawer-hd"><div class="dt">目录</div><div class="r-spacer"></div>
        <button class="icon-btn" data-act="close-toc">${icon('close', 15)}</button></div>
      <div class="drawer-bd" id="toclist"></div>
    </div>

    <div class="drawer right" id="right-drawer">
      <div class="drawer-hd"><div class="dt" id="rdt">书签</div>
        <div class="seg" style="margin-left:auto">
          <button data-act="rtab" data-v="bm" class="on">书签</button>
          <button data-act="rtab" data-v="sr">搜索</button>
        </div>
        <button class="icon-btn" data-act="close-rd">${icon('close', 15)}</button></div>
      <div class="drawer-bd" id="rbody"></div>
    </div>

    <div class="pop" id="pop" style="display:none">
      <div class="pop-head"><span>阅读设置</span>
        <button class="icon-btn" data-act="font" title="关闭">${icon('close', 14)}</button></div>
      <h4>主题</h4>
      <div class="swatches">${THEMES.map((t) => `<div class="swatch ${this.s.theme === t ? 'on' : ''}" data-t="${t}" data-act="ptheme" title="${t}"></div>`).join('')}</div>
      <h4>字体</h4>
      <div class="pop-row"><label>字形</label>
        <select class="sel" id="f-font">${Object.entries(FONT_NAMES).map(([k, v]) => `<option value="${k}" ${this.s.font === k ? 'selected' : ''}>${v}</option>`).join('')}</select></div>
      <div class="pop-row"><label>字号</label><input type="range" id="f-size" min="14" max="30" value="${this.s.size}"><span class="val" id="v-size">${this.s.size}</span></div>
      <div class="pop-row"><label>行距</label><input type="range" id="f-lh" min="1.4" max="2.4" step="0.1" value="${this.s.lineHeight}"><span class="val" id="v-lh">${this.s.lineHeight}</span></div>
      <div class="pop-row"><label>页宽</label><input type="range" id="f-w" min="520" max="1000" step="20" value="${this.s.width}"><span class="val" id="v-w">${this.s.width}</span></div>
      <div class="pop-row"><label>段距</label><input type="range" id="f-para" min="0" max="2" step="0.1" value="${this.s.para}"><span class="val" id="v-para">${this.s.para}</span></div>
      <h4>朗读</h4>
      <div class="pop-row"><label>语音</label><select class="sel" id="t-voice"></select></div>
      <div class="pop-row"><label>语速</label><input type="range" id="t-rate" min="0.5" max="2" step="0.05" value="${(this.s.tts && this.s.tts.rate) || 1}"><span class="val" id="v-rate">${((this.s.tts && this.s.tts.rate) || 1).toFixed(2)}</span></div>
      <div class="pop-row"><label>音调</label><input type="range" id="t-pitch" min="0.5" max="1.6" step="0.05" value="${(this.s.tts && this.s.tts.pitch) || 1}"><span class="val" id="v-pitch">${((this.s.tts && this.s.tts.pitch) || 1).toFixed(2)}</span></div>
      <div class="pop-row"><label>音量</label><input type="range" id="t-vol" min="0" max="1" step="0.05" value="${this.s.tts && this.s.tts.volume != null ? this.s.tts.volume : 1}"><span class="val" id="v-vol">${(this.s.tts && this.s.tts.volume != null ? this.s.tts.volume : 1).toFixed(2)}</span></div>
      <div class="tts-hint" id="tts-hint">语音来自系统，离线可用。想更自然可在此添加语音：Windows 设置 → 时间和语言 → 语音</div>
      <h4>排版</h4>
      <div class="seg" id="f-mode">
        <button data-act="fmode" data-v="page" class="${this.s.mode === 'page' ? 'on' : ''}">翻页</button>
        <button data-act="fmode" data-v="scroll" class="${this.s.mode === 'scroll' ? 'on' : ''}">滚动</button>
      </div>
      <div class="pop-keys">
        <span><kbd>←</kbd><kbd>→</kbd> 翻页</span>
        <span><kbd>空格</kbd> 下一页</span>
        <span><kbd>Ctrl</kbd>+<kbd>F</kbd> 搜索</span>
        <span><kbd>F11</kbd> 全屏</span>
      </div>
    </div>
  </div>`;
  }

  mount() {
    document.body.insertAdjacentHTML('beforeend', this.template());
    this.el = document.getElementById('reader');
    this.$stage = this.$('#stage');
    this.$pv = this.$('#pv');
    this.$flow = this.$('#flow');

    this.$flow.addEventListener('click', (e) => this.onFlowClick(e));
    this.$pv.addEventListener('scroll', () => {
      if (this.s.mode === 'scroll') this._save();
    });
    this.el.addEventListener('mousemove', () => this.poke());
    window.addEventListener('resize', this._onResize);

    this.speaker = new Speaker(this);
    this.fillVoices();
    this.bindWheel();

    this.loadChapter(this.ch, this.curPage, this.scrollRatio);
  }

  /** 滚轮：翻页模式翻页，滚动模式自己滚（点击区挡住了原生滚动，必须手动转发） */
  bindWheel() {
    let acc = 0;
    let lock = 0;
    this.$stage.addEventListener('wheel', (e) => {
      if (e.ctrlKey) return;
      if (this.s.mode === 'scroll') {
        const step = e.deltaMode === 1 ? 20 : e.deltaMode === 2 ? this.$pv.clientHeight : 1;
        this.$pv.scrollTop += e.deltaY * step;
        e.preventDefault();
        return;
      }
      if (this.drawer || this.popOpen) return;
      e.preventDefault();
      const now = Date.now();
      if (now < lock) return;
      acc += e.deltaY;
      if (Math.abs(acc) < 24) return;
      const dir = acc > 0 ? 1 : -1;
      acc = 0;
      lock = now + 220;
      if (dir > 0) this.nextPage();
      else this.prevPage();
    }, { passive: false });
  }

  // ---------------------------------------------------------------- 朗读
  fillVoices() {
    const sel = this.$('#t-voice');
    if (!sel) return;
    const hint = this.$('#tts-hint');
    const DEFAULT_HINT = '语音来自系统，离线可用。想更自然可在此添加语音：Windows 设置 → 时间和语言 → 语音';
    const cur = (this.s.tts && this.s.tts.voice) || '';
    const fill = (list) => {
      if (list.length) {
        if (hint) hint.textContent = DEFAULT_HINT;
      } else if (hint) {
        hint.textContent = '正在读取系统语音…';
      }
      if (!list.length) {
        if (sel.options.length <= 1) sel.innerHTML = '<option value="">（正在读取系统语音…）</option>';
        // 语音列表是异步就绪的，稍后再试
        setTimeout(() => {
          const again = listVoices();
          if (again.length) fill(again);
          else if (hint) hint.textContent = '没有检测到可用语音。请在 Windows 设置 → 时间和语言 → 语音 中添加语音包。';
        }, 1200);
        return;
      }
      sel.innerHTML = list
        .map((v) => `<option value="${esc(v.id)}" ${v.id === cur ? 'selected' : ''}>${esc(v.label)}</option>`)
        .join('');
      if (!cur || !list.some((v) => v.id === cur)) {
        sel.value = list[0].id;
        this.saveTts({ voice: list[0].id });
      }
    };
    if (ttsSupported()) onVoicesReady(fill);
    else fill([]);
  }

  saveTts(patch) {
    patchSettings({ tts: { ...(this.s.tts || {}), ...patch } });
  }

  notify(msg) {
    toast(msg, 2600);
  }

  onSpeakState() {
    const sp = this.speaker;
    const bar = this.$('#ttsbar');
    if (bar) bar.hidden = !sp.active;
    const btn = this.$('[data-act="tts"]');
    if (btn) {
      btn.innerHTML = icon(sp.active ? 'speaker-wave' : 'speaker', 17);
      btn.classList.toggle('on', !!sp.active);
      btn.title = sp.active ? '停止朗读' : '语音朗读';
    }
    const tg = this.$('[data-act="tts-toggle"]');
    if (tg) {
      tg.innerHTML = icon(sp.paused ? 'play' : 'pause', 15);
      tg.title = sp.paused ? '继续' : '暂停';
    }
    if (bar) bar.classList.toggle('paused', !!sp.paused);
  }

  updateSpeakUI(cur, total) {
    const p = this.$('#ttsprog');
    if (!p) return;
    p.textContent = cur && total ? `正在朗读 ${cur} / ${total}` : '正在朗读';
  }

  /** 朗读跟随：滚动模式滚动到可见，翻页模式自动翻到该段落所在页 */
  followSpeak(el) {
    if (!el) return;
    const pv = this.$pv;
    const box = pv.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    if (this.s.mode === 'scroll') {
      if (r.top < box.top + 40 || r.bottom > box.bottom - 40) {
        const target = pv.scrollTop + (r.top - box.top) - box.height * 0.35;
        pv.scrollTo({ top: Math.max(0, target), behavior: 'smooth' });
      }
      return;
    }
    if (this.loading) return;
    const step = this.step || 1;
    if (r.top < box.top - 2 || r.bottom > box.bottom + 2 || r.left < box.left - 2 || r.right > box.right + 2) {
      const delta = Math.round((r.left - box.left) / step);
      const page = Math.max(0, Math.min(this.pages - 1, this.curPage + delta));
      if (page !== this.curPage) this.goPage(page);
    }
  }

  /** 本章读完：还有下一章就自动续读 */
  speakNextChapter() {
    if (this.ch >= this.total - 1) {
      this.notify('已读完全书');
      return false;
    }
    this._keepSpeaking = true;
    this.loadChapter(this.ch + 1, 0);
    return true;
  }

  destroy() {
    clearTimeout(this._imt);
    window.removeEventListener('resize', this._onResize);
    if (this.speaker) this.speaker.stop('destroy');
    this._saveNow();
    if (this.el) this.el.remove();
  }

  // ---------------------------------------------------------------- 章节加载与分页

  async loadChapter(idx, page = 0, scrollRatio = 0) {
    if (this.loading) {
      // 正在加载：延后重试，不丢操作
      setTimeout(() => this.loadChapter(idx, page, scrollRatio), 150);
      return;
    }
    if (this.speaker && this.speaker.active && !this._keepSpeaking) this.speaker.stop('chapter-change');
    this.loading = true;
    this.$('#loading').style.display = 'grid';
    try {
      const data = await api.chapter(this.meta.id, idx, this.s.convert);
      this.ch = idx;
      this.total = data.total;
      this.chTitle = data.title;
      // Markdown 单篇自带标题，不再重复加章节头
      const skipHead = this.meta.kind === 'md' && data.total === 1;
      this.$flow.innerHTML =
        (skipHead ? '' : `<div class="ch-head"><div class="ch-title">${esc(data.title)}</div><div class="ch-rule"></div></div>`) +
        data.html;
      this.renderMath();
      if (this.s.mode === 'scroll') {
        this.$stage.classList.add('scroll');
        requestAnimationFrame(() => {
          const max = this.$pv.scrollHeight - this.$pv.clientHeight;
          this.$pv.scrollTop = scrollRatio * max;
          this.updateChrome();
          this._save();
        });
      } else {
        this.$stage.classList.remove('scroll');
        this.relayout();
        this.goPage(page, true);
      }
      this.renderToc();
      this.updateChrome();
      this._save();
    } catch (e) {
      toast(e.message);
    } finally {
      this.loading = false;
      this.$('#loading').style.display = 'none';
      if (this._keepSpeaking) {
        this._keepSpeaking = false;
        if (this.speaker) this.speaker.continueAfterChapter();
      }
    }
  }

  relayout() {
    if (this.s.mode === 'scroll') {
      this.pages = 1;
      return;
    }
    const flow = this.$flow;
    const cs = getComputedStyle(flow);
    // 真正可用于排字的内宽 = 元素宽度 - 左右内边距（内边距就是纸面留白）
    const padX = (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0);
    const w = Math.max(200, flow.clientWidth - padX);
    flow.style.columnWidth = w + 'px';
    const gap = parseFloat(cs.columnGap) || 0;
    this.step = w + gap;
    // scrollWidth 含左右内边距，先减掉再算栏数
    const content = Math.max(0, flow.scrollWidth - padX);
    this.pages = Math.max(1, Math.ceil(content / this.step));
    this.goPage(Math.min(this.curPage, this.pages - 1), true);
  }

  goPage(n, silent = false) {
    this.curPage = Math.max(0, Math.min(this.pages - 1, n));
    if (this.s.mode !== 'scroll' && this.step) {
      this.$flow.style.transform = `translateX(${-this.curPage * this.step}px)`;
    }
    this.updateChrome();
    if (!silent) this._save();
  }

  nextPage() {
    if (this.loading) {
      setTimeout(() => this.nextPage(), 150);
      return;
    }
    if (this.s.mode === 'scroll') {
      this.$pv.scrollBy({ top: this.$pv.clientHeight * 0.92, behavior: 'smooth' });
      return;
    }
    if (this.curPage < this.pages - 1) this.goPage(this.curPage + 1);
    else if (this.ch < this.total - 1) this.loadChapter(this.ch + 1, 0);
  }

  prevPage() {
    if (this.loading) {
      setTimeout(() => this.prevPage(), 150);
      return;
    }
    if (this.s.mode === 'scroll') {
      this.$pv.scrollBy({ top: -this.$pv.clientHeight * 0.92, behavior: 'smooth' });
      return;
    }
    if (this.curPage > 0) this.goPage(this.curPage - 1);
    else if (this.ch > 0) this.loadChapter(this.ch - 1, 99999);
  }

  reloadKeepPos() {
    const ratio = this.s.mode === 'scroll'
      ? this.$pv.scrollTop / Math.max(1, this.$pv.scrollHeight - this.$pv.clientHeight)
      : 0;
    this.loadChapter(this.ch, this.curPage, ratio);
  }

  // ---------------------------------------------------------------- 状态显示

  pct() {
    const within = this.s.mode === 'scroll'
      ? this.$pv.scrollTop / Math.max(1, this.$pv.scrollHeight - this.$pv.clientHeight)
      : (this.pages > 1 ? this.curPage / (this.pages - 1) : 1);
    if (this.total <= 1) return Math.min(1, Math.max(0, within));
    return Math.min(1, Math.max(0, (this.ch + within) / this.total));
  }

  updateChrome() {
    const t = this.$('#rtitle');
    if (t) t.innerHTML = `<b>${esc(this.meta.title)}</b> <span style="color:var(--text-3)">·</span> ${esc(this.chTitle || '')}`;
    const cn = this.$('#chname');
    if (cn) cn.textContent = this.chTitle || '';
    const pl = this.$('#pglabel');
    if (pl) pl.textContent = this.s.mode === 'scroll'
      ? `${Math.round(this.pct() * 100)}%`
      : `${this.curPage + 1} / ${this.pages}`;
    const sl = this.$('#pgsld');
    if (sl && document.activeElement !== sl) sl.value = String(Math.round(this.pct() * 1000));
    this.el.querySelectorAll('.toc-item').forEach((n) => {
      n.classList.toggle('on', Number(n.dataset.i) === this.ch);
    });
  }

  _saveNow() {
    const max = this.$pv.scrollHeight - this.$pv.clientHeight;
    api.progress(this.meta.id, {
      chapter: this.ch,
      page: this.curPage,
      scroll: max > 0 ? this.$pv.scrollTop / max : 0,
      pct: this.pct(),
    }).catch(() => {});
  }

  // ---------------------------------------------------------------- 目录 / 书签 / 搜索

  renderToc() {
    const list = this.$('#toclist');
    if (!list) return;
    list.innerHTML = this.toc.map((t, i) => `
      <div class="toc-item ${i === this.ch ? 'on' : ''}" data-act="toc-item" data-i="${i}">
        <span class="ti">${i + 1}</span><span class="tt">${esc(t.title)}</span>
      </div>`).join('');
    const on = list.querySelector('.on');
    if (on) on.scrollIntoView({ block: 'nearest' });
  }

  renderBookmarks() {
    this.$('#rdt').textContent = '书签';
    const body = this.$('#rbody');
    if (!this.bookmarks.length) {
      body.innerHTML = `<div class="sr-empty">还没有书签<br>阅读时点顶栏的书签图标即可留下标记</div>`;
      return;
    }
    body.innerHTML = `<div class="search-res">${this.bookmarks.map((b) => `
      <div class="bm-item" data-act="bm-item" data-ch="${b.chapter}">
        <div class="bm-label">${icon('bookmark-f', 12)}${esc(b.label || '书签')}</div>
        <div class="bm-ex">${esc(b.excerpt)}</div>
        <div class="bm-meta">${new Date(b.created * 1000).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
          <button class="bm-del" data-act="bm-del" data-id="${b.id}" title="删除">${icon('trash', 13)}</button>
        </div>
      </div>`).join('')}</div>`;
  }

  async addBookmark() {
    const label = this.s.mode === 'scroll'
      ? `${this.chTitle} · ${Math.round(this.pct() * 100)}%`
      : `${this.chTitle} · 第 ${this.curPage + 1} 页`;
    try {
      const res = await api.addBookmark(this.meta.id, {
        chapter: this.ch,
        loc: label,
        label: '书签',
        excerpt: this.visibleText(60),
      });
      this.bookmarks = res.bookmarks;
      this.openRight('bm');
      toast('已添加书签');
    } catch (e) {
      toast(e.message);
    }
  }

  visibleText(n) {
    const txt = this.$flow.textContent.replace(/\s+/g, ' ').trim();
    const ratio = this.pct();
    const pos = Math.floor(txt.length * ratio);
    return txt.slice(Math.max(0, pos - 8), pos + n) || txt.slice(0, n);
  }

  openRight(tab) {
    this.drawer = 'right';
    this.rightTab = tab;
    this.$('#toc-drawer').classList.remove('open');
    this.$('#right-drawer').classList.add('open');
    this.el.querySelectorAll('[data-act="rtab"]').forEach((b) => b.classList.toggle('on', b.dataset.v === tab));
    if (tab === 'bm') this.renderBookmarks();
    else this.renderSearchBox();
    this.pokeClear();
  }

  renderSearchBox() {
    this.$('#rdt').textContent = '搜索';
    this.$('#rbody').innerHTML = `
      <div style="display:flex;gap:8px;padding:4px 2px 12px">
        <div class="search-box" style="flex:1;width:auto">${icon('search', 15)}<input id="srinput" placeholder="在本书中搜索" value="${esc(this.kw)}"></div>
        <button class="btn primary" data-act="do-search">搜索</button>
      </div>
      <div class="search-res" id="srres"><div class="sr-empty">输入关键词后回车</div></div>`;
    const input = this.$('#srinput');
    input.focus();
    input.addEventListener('keydown', (e) => {
      e.stopPropagation();
      if (e.key === 'Enter') this.runSearch();
    });
    input.addEventListener('input', () => { this.kw = input.value; });
  }

  async runSearch() {
    const kw = (this.$('#srinput')?.value || '').trim();
    if (!kw) return;
    this.kw = kw;
    const res = this.$('#srres');
    res.innerHTML = `<div class="sr-empty"><div class="spin"></div></div>`;
    try {
      const { results } = await api.search(this.meta.id, kw, this.s.convert);
      if (!results.length) {
        res.innerHTML = `<div class="sr-empty">没有找到「${esc(kw)}」</div>`;
        return;
      }
      res.innerHTML = results.map((r) => `
        <div class="sr-item" data-act="sr-jump" data-ch="${r.chapter}">
          <div class="sr-ch">${esc(r.title)}</div>
          <div class="sr-ex">${this.hl(r.excerpt, kw)}</div>
        </div>`).join('');
    } catch (e) {
      res.innerHTML = `<div class="sr-empty">${esc(e.message)}</div>`;
    }
  }

  hl(text, kw) {
    const idx = text.toLowerCase().indexOf(kw.toLowerCase());
    if (idx < 0) return esc(text);
    return esc(text.slice(0, idx)) + '<mark>' + esc(text.slice(idx, idx + kw.length)) + '</mark>' + esc(text.slice(idx + kw.length));
  }

  highlightInFlow(kw) {
    const flow = this.$flow;
    flow.querySelectorAll('mark.hl').forEach((m) => m.replaceWith(document.createTextNode(m.textContent)));
    flow.normalize();
    const lower = kw.toLowerCase();
    const walker = document.createTreeWalker(flow, NodeFilter.SHOW_TEXT);
    const targets = [];
    while (walker.nextNode()) {
      const n = walker.currentNode;
      if (n.nodeValue && n.nodeValue.toLowerCase().includes(lower)) targets.push(n);
    }
    for (const n of targets) {
      const text = n.nodeValue;
      const idx = text.toLowerCase().indexOf(lower);
      const after = n.splitText(idx);
      const rest = after.splitText(kw.length);
      const mark = document.createElement('mark');
      mark.className = 'hl';
      mark.textContent = after.nodeValue;
      after.replaceWith(mark);
      void rest;
    }
    this.relayout();
  }

  // ---------------------------------------------------------------- 链接与公式

  onFlowClick(e) {
    const a = e.target.closest('a');
    if (!a) return;
    e.preventDefault();
    const goto = a.dataset.goto;
    if (goto !== undefined && goto !== '') {
      const [chStr, frag] = String(goto).split(':');
      const ch = parseInt(chStr, 10);
      if (!isNaN(ch) && ch !== this.ch) {
        this.loadChapter(ch, 0);
        return;
      }
      if (frag) this.jumpAnchor(frag);
      return;
    }
    const href = a.getAttribute('href') || '';
    if (/^https?:/i.test(href)) bridge('open_external', href).catch(() => {});
  }

  jumpAnchor(frag) {
    let el = null;
    try {
      el = this.$flow.querySelector('#' + CSS.escape(frag));
    } catch {
      el = this.$flow.querySelector(`[id="${frag}"]`);
    }
    if (!el) return;
    if (this.s.mode === 'scroll') {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    this.goPage(Math.max(0, Math.round(el.offsetLeft / this.step)));
  }

  renderMath() {
    if (!window.renderMathInElement) return;
    try {
      window.renderMathInElement(this.$flow, {
        delimiters: [
          { left: '$$', right: '$$', display: true },
          { left: '$', right: '$', display: false },
        ],
        throwOnError: false,
      });
    } catch { /* 公式渲染失败不影响阅读 */ }
  }

  // ---------------------------------------------------------------- 沉浸模式

  poke() {
    if (this.drawer || this.popOpen) return;
    this.el.classList.remove('immersive');
    clearTimeout(this._imt);
    this._imt = setTimeout(() => {
      if (!this.drawer && !this.popOpen) this.el.classList.add('immersive');
    }, 2800);
  }

  pokeClear() {
    clearTimeout(this._imt);
    this.el.classList.remove('immersive');
  }

  // ---------------------------------------------------------------- 事件

  onAction(name, el) {
    switch (name) {
      case 'back': location.hash = '#/library'; break;
      case 'toc':
        if (this.drawer === 'toc') this.closeDrawers();
        else {
          this.drawer = 'toc';
          this.$('#right-drawer').classList.remove('open');
          this.$('#toc-drawer').classList.add('open');
          this.renderToc();
          this.pokeClear();
        }
        break;
      case 'search': this.openRight('sr'); break;
      case 'bookmark': this.addBookmark(); break;
      case 'tts':
        if (this.speaker.active) this.speaker.stop('user');
        else {
          this.speaker.startFromVisible();
          if (this.speaker.active) this.pokeClear();
        }
        break;
      case 'tts-toggle':
        if (this.speaker.paused) this.speaker.resume();
        else this.speaker.pause();
        break;
      case 'tts-prev': this.speaker.prev(); break;
      case 'tts-next': this.speaker.next(); break;
      case 'tts-stop': this.speaker.stop(); break;
      case 'font': this.togglePop(); break;
      case 'fullscreen': bridge('window_action', 'fullscreen').catch(() => {}); break;
      case 'prev': this.prevPage(); break;
      case 'next': this.nextPage(); break;
      case 'chrome':
        // 面板/抽屉开着时，点正文先收起面板，而不是把工具栏一起藏掉
        if (this.popOpen) {
          this.togglePop(false);
          break;
        }
        if (this.drawer) {
          this.closeDrawers();
          break;
        }
        this.el.classList.add('immersive');
        clearTimeout(this._imt);
        break;
      case 'prev-ch': this.loadChapter(Math.max(0, this.ch - 1), 0); break;
      case 'next-ch': this.loadChapter(Math.min(this.total - 1, this.ch + 1), 0); break;
      case 'close-toc':
      case 'close-rd': this.closeDrawers(); break;
      case 'toc-item':
        this.loadChapter(Number(el.dataset.i), 0);
        this.closeDrawers();
        break;
      case 'rtab': this.openRight(el.dataset.v); break;
      case 'do-search': this.runSearch(); break;
      case 'sr-jump': {
        const ch = Number(el.dataset.ch);
        this.closeDrawers();
        this.loadChapter(ch, 0).then(() => this.kw && this.highlightInFlow(this.kw));
        break;
      }
      case 'bm-del': {
        const id = el.dataset.id;
        api.delBookmark(this.meta.id, id).then((res) => {
          this.bookmarks = res.bookmarks;
          this.renderBookmarks();
        }).catch(() => {});
        break;
      }
      case 'bm-item': {
        const ch = Number(el.dataset.ch);
        this.closeDrawers();
        this.loadChapter(ch, 0);
        break;
      }
      case 'ptheme': {
        const t = el.dataset.t;
        patchSettings({ theme: t });
        this.el.querySelectorAll('.swatch').forEach((s) => s.classList.toggle('on', s.dataset.t === t));
        break;
      }
      case 'fmode': {
        const mode = el.dataset.v;
        patchSettings({ mode });
        this.el.querySelectorAll('#f-mode button').forEach((b) => b.classList.toggle('on', b.dataset.v === mode));
        this.reloadKeepPos();
        break;
      }
      default: break;
    }
  }

  closeDrawers() {
    this.drawer = null;
    this.$('#toc-drawer').classList.remove('open');
    this.$('#right-drawer').classList.remove('open');
  }

  togglePop(force) {
    this.popOpen = force === undefined ? !this.popOpen : !!force;
    const pop = this.$('#pop');
    if (pop) pop.style.display = this.popOpen ? 'block' : 'none';
    const btn = this.$('[data-act="font"]');
    if (btn) btn.classList.toggle('on', this.popOpen);
    if (this.popOpen) this.pokeClear();
  }

  onChange(el) {
    if (el.id === 'cvt') {
      patchSettings({ convert: el.value });
      this.reloadKeepPos();
    } else if (el.id === 'f-font') {
      patchSettings({ font: el.value });
    } else if (el.id === 't-voice') {
      this.saveTts({ voice: el.value });
      if (this.speaker && this.speaker.active) this.speaker.play(this.speaker.idx);
    } else if (el.id === 'pgsld') {
      const o = Number(el.value) / 1000;
      const pos = o * this.total;
      const ch = Math.min(this.total - 1, Math.floor(pos));
      this.loadChapter(ch, 0).then(() => {
        const within = pos - ch;
        if (this.s.mode === 'scroll') {
          const max = this.$pv.scrollHeight - this.$pv.clientHeight;
          this.$pv.scrollTop = within * max;
        } else {
          this.goPage(Math.round(within * (this.pages - 1)));
        }
      });
    }
  }

  onInput(el) {
    const ttsMap = {
      't-rate': ['rate', 'v-rate'],
      't-pitch': ['pitch', 'v-pitch'],
      't-vol': ['volume', 'v-vol'],
    };
    if (ttsMap[el.id]) {
      const [key, valId] = ttsMap[el.id];
      const val = parseFloat(el.value);
      this.saveTts({ [key]: val });
      const v = this.$('#' + valId);
      if (v) v.textContent = val.toFixed(2);
      if (this.speaker && this.speaker.active) this.speaker.play(this.speaker.idx); // 立即生效
      return;
    }
    const map = {
      'f-size': ['size', 'v-size', false],
      'f-lh': ['lineHeight', 'v-lh', true],
      'f-w': ['width', 'v-w', false],
      'f-para': ['para', 'v-para', true],
    };
    const m = map[el.id];
    if (!m) return;
    const [key, valId, isFloat] = m;
    const val = isFloat ? parseFloat(el.value) : parseInt(el.value, 10);
    patchSettings({ [key]: val });
    const v = this.$('#' + valId);
    if (v) v.textContent = val;
    this.relayout();
  }

  onKey(e) {
    if (e.target.matches('input, select, textarea')) return;
    if (e.ctrlKey && (e.key === 'f' || e.key === 'F')) {
      e.preventDefault();
      this.openRight('sr');
      return;
    }
    switch (e.key) {
      case 'ArrowRight':
      case ' ':
      case 'PageDown':
        e.preventDefault();
        this.nextPage();
        break;
      case 'ArrowLeft':
      case 'PageUp':
        e.preventDefault();
        this.prevPage();
        break;
      case 'Home': e.preventDefault(); this.loadChapter(0, 0); break;
      case 'End': e.preventDefault(); this.loadChapter(this.total - 1, 99999); break;
      case 'Escape': location.hash = '#/library'; break;
      case 'F11':
        e.preventDefault();
        bridge('window_action', 'fullscreen').catch(() => {});
        break;
      case '+':
      case '=':
        patchSettings({ size: Math.min(30, this.s.size + 1) });
        this.relayout();
        break;
      case '-':
        patchSettings({ size: Math.max(14, this.s.size - 1) });
        this.relayout();
        break;
      default: break;
    }
  }
}

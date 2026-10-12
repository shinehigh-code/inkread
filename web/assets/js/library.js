// 书库视图
import { api, bridge } from './api.js';
import { icon, esc, toast, fmtSize, fmtTime, coverColor } from './ui.js';

function emptyState() {
  return `<div class="empty">
    <svg viewBox="0 0 120 120" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
      <rect x="20" y="24" width="18" height="60" rx="2.5"/>
      <rect x="42" y="32" width="15" height="52" rx="2.5"/>
      <rect x="61" y="20" width="21" height="64" rx="2.5"/>
      <rect x="86" y="36" width="14" height="48" rx="2.5"/>
      <path d="M25 34h8M25 42h8M47 42h6M67 30h9M67 38h9"/>
      <path d="M10 88h100"/>
      <path d="M30 84v8M60 84v8M90 84v8"/>
    </svg>
    <div class="et">书架还是空的</div>
    <div class="es">支持 TXT / MD / EPUB / CBZ / CBR / 7Z / CBT 与图片文件夹。点右上角「添加图书」或直接把书拖进来，文件只在本地读取，不上传任何数据。</div>
  </div>`;
}

export class LibraryView {
  constructor(app, scope = 'library') {
    this.app = app;
    this.scope = scope;
    this.sort = 'recent';
    this.q = '';
    this.layout = localStorage.getItem('inkread.layout') || 'grid';
  }

  mount() {
    const m = this.app.main;
    m.innerHTML = `
      <div class="lib-head">
        <div class="lib-title">${this.scope === 'recent' ? '最近阅读' : '全部图书'}<small id="libcount"></small></div>
        <div class="lib-tools">
          <div class="search-box">${icon('search', 15)}<input id="libq" placeholder="搜索书名" value="${esc(this.q)}"></div>
          <select class="sel" id="libsort">
            <option value="recent">最近阅读</option>
            <option value="title">按书名</option>
            <option value="added">按添加时间</option>
          </select>
          <div class="seg" id="liblayout">
            <button data-v="grid" class="${this.layout === 'grid' ? 'on' : ''}" title="网格">${icon('grid', 14)}</button>
            <button data-v="list" class="${this.layout === 'list' ? 'on' : ''}" title="列表">${icon('rows', 14)}</button>
          </div>
          <button class="btn primary" data-act="add-files">${icon('plus', 14)}添加图书</button>
        </div>
      </div>
      <div class="lib-body" id="libbody"></div>`;
    this.$body = m.querySelector('#libbody');
    m.querySelector('#libsort').value = this.sort;
    this.refresh();
  }

  async refresh() {
    try {
      const data = await api.library(this.sort, this.q);
      this.app.state.books = data.books;
      this.render();
    } catch (e) {
      toast(e.message);
    }
  }

  metaLine(b) {
    const parts = [];
    if (b.author) parts.push(b.author);
    if (b.kind === 'comic') parts.push(`${b.pages || '?'} 页`);
    else parts.push(`${b.chapters || '?'} 章`);
    if (b.size) parts.push(fmtSize(b.size));
    return parts.join(' · ');
  }

  coverHtml(b, cls = '') {
    const pct = Math.round((b.progress?.pct || 0) * 100);
    const inner = b.has_cover
      ? `<img src="${api.cover(b.id)}" alt="" loading="lazy">`
      : `<div class="gen-title">${esc(b.title)}</div><div class="gen-author">${esc(b.author || b.fmt.toUpperCase())}</div>`;
    const style = b.has_cover ? '' : ` style="background:${coverColor(b.title)}"`;
    return `<div class="cover ${cls}${b.has_cover ? '' : ' gen'}"${style}>
      ${inner}
      <div class="spine"></div>
      <span class="fmt-badge">${esc(b.fmt)}</span>
      ${pct > 0 ? `<div class="prog"><i style="width:${pct}%"></i></div>` : ''}
      <button class="del" data-act="del" data-id="${b.id}" title="移出书库">${icon('trash', 13)}</button>
    </div>`;
  }

  continueCard(b) {
    const pct = Math.round((b.progress?.pct || 0) * 100);
    const cover = b.has_cover
      ? `<img src="${api.cover(b.id)}" alt="">`
      : esc(b.title.slice(0, 2));
    return `<div class="continue-card" data-act="open" data-id="${b.id}">
      <div class="cc-cover" style="background:${coverColor(b.title)}">${cover}</div>
      <div class="cc-info">
        <div class="cc-label">继续阅读</div>
        <div class="cc-title">${esc(b.title)}</div>
        <div class="cc-sub">${esc([b.author, b.fmt.toUpperCase(), `已读 ${pct}%`, fmtTime(b.last_read)].filter(Boolean).join(' · '))}</div>
        <div class="cc-bar"><i style="width:${pct}%"></i></div>
      </div>
      ${icon('chev-r', 18)}
    </div>`;
  }

  render() {
    const books = this.app.state.books;
    const count = this.app.main.querySelector('#libcount');
    if (count) count.textContent = books.length ? `${books.length} 本` : '';
    if (!books.length) {
      this.$body.innerHTML = emptyState();
      return;
    }
    let html = '';
    if (this.scope !== 'recent') {
      const recent = books.find((b) => (b.progress?.pct || 0) > 0);
      if (recent) html += this.continueCard(recent);
    }
    if (this.layout === 'grid') {
      html += `<div class="grid">${books.map((b) => `
        <div class="book" data-act="open" data-id="${b.id}">
          ${this.coverHtml(b)}
          <div class="book-name">${esc(b.title)}</div>
          <div class="book-meta">${esc(this.metaLine(b))}</div>
        </div>`).join('')}</div>`;
    } else {
      html += `<div class="list-rows">${books.map((b) => {
        const pct = Math.round((b.progress?.pct || 0) * 100);
        const cover = b.has_cover
          ? `<img src="${api.cover(b.id)}" alt="">`
          : esc(b.title.slice(0, 1));
        return `<div class="list-row" data-act="open" data-id="${b.id}">
          <div class="lr-cover" style="background:${coverColor(b.title)}">${cover}</div>
          <div class="lr-name">${esc(b.title)}</div>
          <div class="lr-meta">${esc(this.metaLine(b))}</div>
          <div class="lr-prog"><div class="lr-bar"><i style="width:${pct}%"></i></div></div>
        </div>`;
      }).join('')}</div>`;
    }
    this.$body.innerHTML = html;
  }

  onAction(name, el) {
    if (name === 'open') {
      const host = el.closest('[data-id]');
      if (host) location.hash = `#/read/${host.dataset.id}`;
    } else if (name === 'del') {
      const id = el.dataset.id;
      api.removeBook(id).then(() => {
        this.app.state.books = this.app.state.books.filter((b) => b.id !== id);
        this.render();
        toast('已移出书库（源文件未删除）');
      }).catch((e) => toast(e.message));
    }
  }

  onChange(el) {
    if (el.id === 'libsort') {
      this.sort = el.value;
      this.refresh();
    } else if (el.id === 'libq') {
      this.q = el.value.trim();
      this.refresh();
    }
  }

  onInput(el) {
    if (el.id === 'libq') {
      const v = el.value.trim();
      clearTimeout(this._qt);
      this._qt = setTimeout(() => { this.q = v; this.refresh(); }, 250);
    }
  }

  onClickSeg(el) {
    if (el.dataset.v && el.parentElement?.id === 'liblayout') {
      this.layout = el.dataset.v;
      localStorage.setItem('inkread.layout', this.layout);
      this.app.main.querySelectorAll('#liblayout button').forEach((b) => b.classList.toggle('on', b.dataset.v === this.layout));
      this.render();
    }
  }

  destroy() {
    clearTimeout(this._qt);
  }
}

// 应用外壳：标题栏 / 侧栏 / 路由 / 全局事件 / 设置页
import { api, bridge } from './api.js';
import { icon, esc, toast, applySettings, patchSettings, FONTS, FONT_NAMES, CONVERT_NAMES } from './ui.js';
import { LibraryView } from './library.js';
import { TextReader } from './reader.js';
import { ComicReader } from './comic.js';

export const state = {
  settings: null,
  books: [],
  currentView: null,
};

export const app = { state, main: null };

// ---------------------------------------------------------------- 外壳

function shell() {
  return `
  <div class="titlebar">
    <div class="brand"><div class="logo">墨</div><div class="name">墨读</div><div class="tag">本地阅读器</div></div>
    <div class="win-ctl">
      <button data-act="win" data-a="minimize" title="最小化">${icon('min', 15)}</button>
      <button data-act="win" data-a="toggle-maximize" title="最大化">${icon('max', 14)}</button>
      <button class="close" data-act="win" data-a="close" title="关闭">${icon('close', 15)}</button>
    </div>
  </div>
  <div class="shell">
    <aside class="sidebar">
      <div class="side-scroll">
        <div class="nav-item" data-nav="library">${icon('book', 17)}<span>全部图书</span><span class="count" id="navcount"></span></div>
        <div class="nav-item" data-nav="recent">${icon('clock', 17)}<span>最近阅读</span></div>
      </div>
      <div class="side-foot">
        <button class="btn primary block" data-act="add-files">${icon('plus', 14)}<span>添加图书</span></button>
        <button class="btn ghost block" data-act="add-folder" style="margin-top:6px">${icon('folder', 14)}<span>导入文件夹</span></button>
        <div class="nav-item" data-nav="settings" style="margin-top:6px">${icon('sliders', 17)}<span>设置</span></div>
      </div>
    </aside>
    <div class="main" id="main"></div>
  </div>`;
}

// ---------------------------------------------------------------- 路由

function route() {
  const h = (location.hash || '#/library').replace(/^#\//, '');
  const [name, arg] = h.split('/');
  if (state.currentView?.destroy) state.currentView.destroy();
  document.body.classList.remove('has-reader');
  if (name === 'read' && arg) {
    openReader(arg);
  } else if (name === 'settings') {
    state.currentView = new SettingsView();
    state.currentView.mount();
  } else {
    state.currentView = new LibraryView(app, name === 'recent' ? 'recent' : 'library');
    state.currentView.mount();
  }
  document.querySelectorAll('.nav-item').forEach((n) => {
    n.classList.toggle('active', n.dataset.nav === (name || 'library'));
  });
  const c = document.getElementById('navcount');
  if (c) c.textContent = state.books.length ? String(state.books.length) : '';
}

async function openReader(id) {
  let info;
  try {
    info = await api.book(id);
  } catch (e) {
    toast(e.message);
    location.hash = '#/library';
    return;
  }
  const View = info.meta.kind === 'comic' ? ComicReader : TextReader;
  const v = new View(app, info);
  state.currentView = v;
  v.mount();
  document.body.classList.add('has-reader');
  document.querySelectorAll('.nav-item').forEach((n) => n.classList.remove('active'));
}

// ---------------------------------------------------------------- 添加图书

async function addFiles() {
  let paths = [];
  try {
    paths = await bridge('open_files');
  } catch (e) {
    toast('无法打开文件选择窗口');
    return;
  }
  if (!paths || !paths.length) return;
  await doAdd(paths);
}

async function addFolder() {
  let folder = null;
  try {
    folder = await bridge('open_folder');
  } catch (e) {
    toast('无法打开文件夹选择窗口');
    return;
  }
  if (!folder) return;
  await doAdd([folder]);
}

async function doAdd(paths) {
  try {
    const res = await api.addBooks(paths);
    let msg = `已添加 ${res.added.length} 本`;
    if (res.errors.length) msg += `，${res.errors.length} 个无法识别`;
    toast(msg, 2600);
    if (state.currentView instanceof LibraryView) state.currentView.refresh();
    else location.hash = '#/library';
    const c = document.getElementById('navcount');
    if (c) c.textContent = String(state.books.length + res.added.length);
  } catch (e) {
    toast(e.message);
  }
}

// ---------------------------------------------------------------- 全局事件

const WIN_ACTIONS = {
  win(el) {
    bridge('window_action', el.dataset.a).catch(() => {});
  },
  'add-files': addFiles,
  'add-folder': addFolder,
};

function onClick(e) {
  const nav = e.target.closest('[data-nav]');
  if (nav) {
    location.hash = '#/' + nav.dataset.nav;
    return;
  }
  const act = e.target.closest('[data-act]');
  if (!act) return;
  const name = act.dataset.act;
  if (WIN_ACTIONS[name]) {
    WIN_ACTIONS[name](act, e);
    return;
  }
  const v = state.currentView;
  if (v && v.onAction) v.onAction(name, act, e);
}

function onChange(e) {
  const el = e.target;
  const v = state.currentView;
  if (v && v.onChange) v.onChange(el, e);
}

function onInput(e) {
  const el = e.target;
  const v = state.currentView;
  if (v && v.onInput) v.onInput(el, e);
}

function onKey(e) {
  const v = state.currentView;
  if (v && v.onKey) v.onKey(e);
}

/** 双击标题栏/阅读器工具栏：切换最大化与还原（跟普通窗口一致） */
function onDblClick(e) {
  const bar = e.target.closest('.titlebar, .r-bar');
  const topEdge = e.target.classList && e.target.classList.contains('rz-n'); // 顶部边缘热区也允许双击
  if (!bar && !topEdge) return;
  if (e.target.closest('button, input, select, textarea, label')) return;
  bridge('window_action', 'toggle-maximize').catch(() => {});
}

/** 无边框窗口没有系统边框，这里铺一层不可见的边缘热区，支持拖拽缩放窗口 */
function initWindowResize() {
  const layer = document.createElement('div');
  layer.className = 'resize-layer';
  layer.innerHTML = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']
    .map((d) => `<div class="rz rz-${d}" data-rz="${d}"></div>`)
    .join('');
  document.body.appendChild(layer);

  let st = null;
  layer.addEventListener('mousedown', (e) => {
    const dir = e.target.dataset && e.target.dataset.rz;
    if (!dir) return;
    e.preventDefault();
    e.stopPropagation();
    bridge('window_bounds')
      .then((b) => {
        if (!b || !b.w) return;
        st = { dir, sx: e.screenX, sy: e.screenY, b, k: window.devicePixelRatio || 1 };
        document.body.classList.add('resizing');
      })
      .catch(() => {});
  });
  window.addEventListener('mousemove', (e) => {
    if (!st) return;
    const k = st.k;
    const dx = (e.screenX - st.sx) * k;
    const dy = (e.screenY - st.sy) * k;
    const b = st.b;
    let { x, y, w, h } = b;
    const minW = 960 * k; // 与窗口最小尺寸（960x600 逻辑像素）保持一致
    const minH = 600 * k;
    if (st.dir.includes('e')) w = Math.max(minW, b.w + dx);
    if (st.dir.includes('s')) h = Math.max(minH, b.h + dy);
    if (st.dir.includes('w')) {
      w = Math.max(minW, b.w - dx);
      x = b.x + (b.w - w);
    }
    if (st.dir.includes('n')) {
      h = Math.max(minH, b.h - dy);
      y = b.y + (b.h - h);
    }
    bridge('window_set_bounds', Math.round(x), Math.round(y), Math.round(w), Math.round(h)).catch(() => {});
  });
  window.addEventListener('mouseup', () => {
    if (!st) return;
    st = null;
    document.body.classList.remove('resizing');
  });
}

// ---------------------------------------------------------------- 设置页

class SettingsView {
  mount() {
    const s = state.settings;
    app.main.innerHTML = `
      <div class="settings-page">
        <div class="set-card">
          <h3>${icon('type', 16)}外观与排版</h3>
          <div class="set-line"><div class="sl-label">主题<div class="sl-desc">影响界面与阅读页配色</div></div>
            <div class="swatches">${['paper', 'ink', 'sepia', 'moss', 'night'].map((t) => `<div class="swatch ${s.theme === t ? 'on' : ''}" data-t="${t}" data-act="theme" title="${t}"></div>`).join('')}</div>
          </div>
          <div class="set-line"><div class="sl-label">正文字体</div>
            <select class="sel" id="set-font">${Object.entries(FONT_NAMES).map(([k, v]) => `<option value="${k}" ${s.font === k ? 'selected' : ''}>${v}</option>`).join('')}</select>
          </div>
          <div class="set-line"><div class="sl-label">字号</div>
            <input type="range" id="set-size" min="14" max="30" step="1" value="${s.size}" style="flex:1"><span class="val" style="font-size:12px;color:var(--text-3);width:28px;text-align:right">${s.size}</span>
          </div>
          <div class="set-line"><div class="sl-label">行距</div>
            <input type="range" id="set-lh" min="1.4" max="2.4" step="0.1" value="${s.lineHeight}" style="flex:1"><span class="val" style="font-size:12px;color:var(--text-3);width:28px;text-align:right">${s.lineHeight}</span>
          </div>
          <div class="set-line"><div class="sl-label">页宽</div>
            <input type="range" id="set-w" min="520" max="1000" step="20" value="${s.width}" style="flex:1"><span class="val" style="font-size:12px;color:var(--text-3);width:36px;text-align:right">${s.width}</span>
          </div>
          <div class="set-line"><div class="sl-label">段距</div>
            <input type="range" id="set-para" min="0" max="2" step="0.1" value="${s.para}" style="flex:1"><span class="val" style="font-size:12px;color:var(--text-3);width:28px;text-align:right">${s.para}</span>
          </div>
          <div class="set-line"><div class="sl-label">阅读方式<div class="sl-desc">翻页为左右分栏，滚动为长页</div></div>
            <div class="seg" id="set-mode">
              <button data-v="page" class="${s.mode === 'page' ? 'on' : ''}">翻页</button>
              <button data-v="scroll" class="${s.mode === 'scroll' ? 'on' : ''}">滚动</button>
            </div>
          </div>
        </div>

        <div class="set-card">
          <h3>${icon('convert', 16)}阅读偏好</h3>
          <div class="set-line"><div class="sl-label">默认繁简<div class="sl-desc">打开书籍时使用的文字形态，阅读器中可随时切换</div></div>
            <select class="sel" id="set-convert">${Object.entries(CONVERT_NAMES).map(([k, v]) => `<option value="${k}" ${s.convert === k ? 'selected' : ''}>${v}</option>`).join('')}</select>
          </div>
        </div>

        <div class="set-card">
          <h3>${icon('image', 16)}漫画默认设置</h3>
          <div class="set-line"><div class="sl-label">缩放模式</div>
            <select class="sel" id="set-fit">
              <option value="fit-height" ${s.comic.fit === 'fit-height' ? 'selected' : ''}>适应高度</option>
              <option value="fit-width" ${s.comic.fit === 'fit-width' ? 'selected' : ''}>适应宽度</option>
              <option value="original" ${s.comic.fit === 'original' ? 'selected' : ''}>原始大小</option>
              <option value="continuous" ${s.comic.fit === 'continuous' ? 'selected' : ''}>连续滚动</option>
            </select>
          </div>
          <div class="set-line"><div class="sl-label">单双页</div>
            <div class="seg" id="set-spread">
              <button data-v="single" class="${s.comic.spread === 'single' ? 'on' : ''}">单页</button>
              <button data-v="double" class="${s.comic.spread === 'double' ? 'on' : ''}">双页</button>
            </div>
          </div>
          <div class="set-line"><div class="sl-label">阅读方向<div class="sl-desc">日系漫画选从右到左</div></div>
            <div class="seg" id="set-dir">
              <button data-v="ltr" class="${s.comic.dir === 'ltr' ? 'on' : ''}>左 → 右</button>
              <button data-v="rtl" class="${s.comic.dir === 'rtl' ? 'on' : ''}>右 → 左</button>
            </div>
          </div>
        </div>

        <div class="set-card">
          <h3>${icon('sliders', 16)}关于</h3>
          <div class="about-line">
            <b>墨读 InkRead</b> 1.0.0 · 本地电子书与漫画阅读器<br>
            支持格式：TXT / Markdown / EPUB / CBZ / CBR / CB7 / CBT / 图片文件夹<br>
            阅读数据保存在本机，软件不发起任何网络请求，不收集任何信息。
          </div>
          <div style="margin-top:16px;display:flex;gap:8px">
            <button class="btn" data-act="open-data">${icon('folder', 14)}打开数据目录</button>
          </div>
        </div>
      </div>`;
  }

  onAction(name, el) {
    if (name === 'theme') {
      const t = el.dataset.t;
      patchSettings({ theme: t });
      app.main.querySelectorAll('.swatch').forEach((s) => s.classList.toggle('on', s.dataset.t === t));
    } else if (name === 'open-data') {
      bridge('open_data_dir').then((d) => toast('数据目录：' + d, 3000)).catch(() => toast('无法打开数据目录'));
    } else if (el.dataset.v && el.parentElement?.id) {
      const seg = el.parentElement.id;
      const key = { 'set-mode': 'mode', 'set-spread': 'comic.spread', 'set-dir': 'comic.dir' }[seg];
      if (key) {
        el.parentElement.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b === el));
        if (key.startsWith('comic.')) {
          const patch = { comic: { ...state.settings.comic, [key.slice(6)]: el.dataset.v } };
          patchSettings(patch);
        } else {
          patchSettings({ [key]: el.dataset.v });
        }
      }
    }
  }

  onChange(el) {
    const map = {
      'set-font': (v) => ({ font: v }),
      'set-convert': (v) => ({ convert: v }),
      'set-fit': (v) => ({ comic: { ...state.settings.comic, fit: v } }),
    };
    if (map[el.id]) patchSettings(map[el.id](el.value));
  }

  onInput(el) {
    const map = {
      'set-size': ['size', Number],
      'set-lh': ['lineHeight', Number],
      'set-w': ['width', Number],
      'set-para': ['para', Number],
    };
    if (map[el.id]) {
      const [key, cast] = map[el.id];
      const val = cast(el.value);
      patchSettings({ [key]: val });
      const valEl = el.parentElement.querySelector('.val');
      if (valEl) valEl.textContent = val;
    }
  }

  destroy() {}
}

// ---------------------------------------------------------------- 启动

async function boot() {
  document.getElementById('app').innerHTML = shell();
  app.main = document.getElementById('main');
  try {
    const s = await api.settings();
    applySettings(s);
    state.settings = s; // 与 ui 模块共享同一引用，patchSettings 原地生效
  } catch (e) {
    toast('本地服务连接失败，请重启应用');
  }
  document.addEventListener('click', onClick);
  document.addEventListener('dblclick', onDblClick);
  document.addEventListener('change', onChange);
  document.addEventListener('input', onInput);
  document.addEventListener('keydown', onKey);
  window.addEventListener('hashchange', route);
  initWindowResize();
  // 预热语音引擎：system voices 要调用一次 getVoices 才会初始化，
  // 在书库阶段就预热，用户第一次打开阅读器时语音列表已经就绪。
  try {
    if (window.speechSynthesis) window.speechSynthesis.getVoices();
  } catch (e) { /* 忽略 */ }
  route();
}

boot();

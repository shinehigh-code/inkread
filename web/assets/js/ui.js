// 图标与通用工具
import { api } from './api.js';

const P = (d, extra = '') => `<path d="${d}" ${extra}/>`;

export const ICONS = {
  back: '<polyline points="15 5 8 12 15 19"/>',
  plus: P('M12 5v14M5 12h14'),
  folder: '<path d="M3 7.5A1.5 1.5 0 0 1 4.5 6h4l2 2h7A1.5 1.5 0 0 1 19 9.5v8A1.5 1.5 0 0 1 17.5 19h-13A1.5 1.5 0 0 1 3 17.5z"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
  close: P('M6 6l12 12M18 6L6 18'),
  min: P('M5 12h14'),
  max: '<rect x="5.5" y="5.5" width="13" height="13" rx="1.5"/>',
  restore: '<rect x="8" y="8" width="11" height="11" rx="1.5"/><path d="M5.5 15.5v-9a1 1 0 0 1 1-1h9"/>',
  book: '<path d="M12 6.5C10.6 4.8 8.2 4 5.5 4.3v13.4c2.7-.3 5.1.5 6.5 2.1 1.4-1.6 3.8-2.4 6.5-2.1V4.3c-2.7-.3-5.1.5-6.5 2.2z"/><path d="M12 6.5v13.3"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  sliders: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2.2"/><circle cx="9" cy="17" r="2.2"/>',
  grid: '<rect x="4" y="4" width="7" height="7" rx="1.2"/><rect x="13" y="4" width="7" height="7" rx="1.2"/><rect x="4" y="13" width="7" height="7" rx="1.2"/><rect x="13" y="13" width="7" height="7" rx="1.2"/>',
  rows: P('M4 6h16M4 12h16M4 18h16'),
  trash: '<path d="M4 7h16M9.5 7V5.5A1.5 1.5 0 0 1 11 4h2a1.5 1.5 0 0 1 1.5 1.5V7M6.5 7l.8 12.1a1.5 1.5 0 0 0 1.5 1.4h6.4a1.5 1.5 0 0 0 1.5-1.4L17.5 7"/>',
  toc: '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="5" cy="6" r="1.2"/><circle cx="5" cy="12" r="1.2"/><circle cx="5" cy="18" r="1.2"/>',
  bookmark: '<path d="M7 4.5h10a1 1 0 0 1 1 1v14l-6-4-6 4v-14a1 1 0 0 1 1-1z"/>',
  'bookmark-f': '<path d="M7 4.5h10a1 1 0 0 1 1 1v14l-6-4-6 4v-14a1 1 0 0 1 1-1z" fill="currentColor"/>',
  type: '<text x="12" y="16.5" text-anchor="middle" font-size="13" font-family="Georgia, serif" fill="currentColor" stroke="none">Aa</text>',
  convert: '<text x="12" y="16.5" text-anchor="middle" font-size="13" font-family="Songti SC, SimSun, serif" fill="currentColor" stroke="none">繁</text>',
  fullscreen: '<path d="M9 4H4v5M15 4h5v5M15 20h5v-5M9 20H4v-5"/>',
  'fullscreen-x': '<path d="M4 9h5V4M20 9V4h-5M20 15v5h-5M4 15v5h5"/>',
  'chev-l': '<path d="M15 5l-7 7 7 7"/>',
  'chev-r': '<path d="M9 5l7 7-7 7"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  image: '<rect x="4" y="4.5" width="16" height="15" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M4 17l5-4.5 3.5 3 3-2.5 4.5 4"/>',
  single: '<rect x="6.5" y="4" width="11" height="16" rx="1.2"/>',
  double: '<rect x="3.5" y="4" width="8" height="16" rx="1.2"/><rect x="12.5" y="4" width="8" height="16" rx="1.2"/>',
  scroll: '<rect x="5.5" y="3.5" width="13" height="17" rx="1.5"/><path d="M9 8h6M9 12h6M9 16h3.5"/>',
  fitw: '<path d="M4 12h16M8 8l-4 4 4 4M16 8l4 4-4 4"/>',
  fith: '<path d="M12 4v16M8 8l4-4 4 4M8 16l4 4 4-4"/>',
  original: '<rect x="4.5" y="4.5" width="15" height="15" rx="1.5"/><path d="M9 9h6v6H9z"/>',
  'arrow-l': '<path d="M20 12H4M8 8l-4 4 4 4"/>',
  'arrow-r': '<path d="M4 12h16M16 8l4 4-4 4"/>',
  external: '<path d="M14 4h6v6M20 4L11 13"/><path d="M18 13.5V19a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5.5"/>',
  refresh: '<path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v4h-4"/>',
  speaker: '<path d="M11 5.6v12.8L6.8 15H4.6A1.6 1.6 0 0 1 3 13.4v-2.8A1.6 1.6 0 0 1 4.6 9h2.2z"/><path d="M14.5 9.5a3.5 3.5 0 0 1 0 5"/>',
  'speaker-wave': '<path d="M11 5.6v12.8L6.8 15H4.6A1.6 1.6 0 0 1 3 13.4v-2.8A1.6 1.6 0 0 1 4.6 9h2.2z"/><path d="M14.5 9.5a3.5 3.5 0 0 1 0 5"/><path d="M17.5 7a7 7 0 0 1 0 10"/>',
  pause: '<rect x="7" y="5.5" width="3.4" height="13" rx="1"/><rect x="13.6" y="5.5" width="3.4" height="13" rx="1"/>',
  play: '<path d="M8 5.6l10.5 6.4L8 18.4z"/>',
};

export function icon(name, size = 18) {
  const body = ICONS[name] || ICONS.book;
  return `<span class="ic"><svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${body}</svg></span>`;
}

export function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

let toastTimer = null;
export function toast(msg, ms = 2200) {
  let el = document.querySelector('.toast');
  if (!el) {
    el = document.createElement('div');
    el.className = 'toast';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  requestAnimationFrame(() => el.classList.add('show'));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), ms);
}

export function debounce(fn, ms) {
  let t = null;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

export function fmtSize(n) {
  if (!n) return '';
  if (n < 1024) return n + ' B';
  if (n < 1048576) return (n / 1024).toFixed(0) + ' KB';
  return (n / 1048576).toFixed(1) + ' MB';
}

export function fmtTime(ts) {
  if (!ts) return '';
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return '刚刚';
  if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前';
  if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前';
  if (diff < 86400 * 30) return Math.floor(diff / 86400) + ' 天前';
  const d = new Date(ts * 1000);
  return `${d.getMonth() + 1}月${d.getDate()}日`;
}

const COVER_COLORS = [
  '#7C8DA6', '#A98B7B', '#7E9B85', '#96889E', '#B0A183',
  '#8494A6', '#A8847E', '#7F9273', '#8C7B9B', '#A99A6E',
  '#6F8577', '#9B8FA6',
];

export function coverColor(title) {
  let h = 0;
  const s = String(title || '');
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return COVER_COLORS[h % COVER_COLORS.length];
}

export const FONTS = {
  song: '"Noto Serif SC","Source Han Serif SC","Songti SC","STSong","SimSun",Georgia,serif',
  kai: '"Kaiti SC","KaiTi","STKaiti","Noto Serif SC",serif',
  hei: '"Noto Sans SC","Source Han Sans SC","SimHei","Microsoft YaHei",sans-serif',
  yahei: '"Microsoft YaHei UI","Microsoft YaHei","PingFang SC",sans-serif',
  georgia: 'Georgia,"Times New Roman","Noto Serif SC",serif',
};

export const FONT_NAMES = { song: '宋体', kai: '楷体', hei: '黑体', yahei: '微软雅黑', georgia: 'Georgia' };

export const CONVERT_NAMES = { none: '原文', t2s: '简体', s2t: '繁體', s2tw: '繁體·台', s2hk: '繁體·港' };

// ---------------------------------------------------------------- 设置应用

let _settingsState = null;
let _saveTimer = null;

export function applySettings(s) {
  _settingsState = s;
  document.documentElement.dataset.theme = s.theme || 'paper';
  const st = document.documentElement.style;
  st.setProperty('--read-size', (s.size || 19) + 'px');
  st.setProperty('--read-lh', String(s.lineHeight || 1.9));
  st.setProperty('--read-w', (s.width || 760) + 'px');
  st.setProperty('--read-font', FONTS[s.font] || FONTS.song);
  st.setProperty('--read-para', (s.para ?? 0.9) + 'em');
}

export function patchSettings(patch) {
  if (!_settingsState) _settingsState = {};
  Object.assign(_settingsState, patch); // 原地修改，阅读器等持有同一引用即可同步
  applySettings(_settingsState);
  clearTimeout(_saveTimer);
  _saveTimer = setTimeout(() => {
    api.saveSettings(patch).catch(() => {});
  }, 250);
}

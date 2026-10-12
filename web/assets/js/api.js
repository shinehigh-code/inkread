// API 封装：全部走本地回环服务
const BASE = '';

async function request(url, options = {}) {
  const r = await fetch(BASE + url, {
    headers: { 'Accept': 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
    ...options,
  });
  let data = null;
  try { data = await r.json(); } catch { /* 二进制接口不返回 JSON */ }
  if (!r.ok) throw new Error((data && data.error) || `请求失败 (${r.status})`);
  return data;
}

export const api = {
  get: (url) => request(url),
  post: (url, body) => request(url, { method: 'POST', body: JSON.stringify(body || {}) }),

  settings: () => request('/api/settings'),
  saveSettings: (patch) => request('/api/settings', { method: 'POST', body: JSON.stringify(patch) }),

  library: (sort = 'recent', q = '') =>
    request(`/api/library?sort=${encodeURIComponent(sort)}&q=${encodeURIComponent(q)}`),
  addBooks: (paths) => request('/api/library/add', { method: 'POST', body: JSON.stringify({ paths }) }),
  removeBook: (id) => request('/api/library/remove', { method: 'POST', body: JSON.stringify({ id }) }),

  book: (id) => request(`/api/book/${id}`),
  chapter: (id, n, mode) => request(`/api/book/${id}/chapter/${n}?mode=${encodeURIComponent(mode || 'none')}`),
  page: (id, n) => `/api/book/${id}/page/${n}`,
  cover: (id) => `/api/book/${id}/cover`,
  progress: (id, p) => request(`/api/book/${id}/progress`, { method: 'POST', body: JSON.stringify(p) }),
  bookmarks: (id) => request(`/api/book/${id}/bookmarks`),
  addBookmark: (id, bm) => request(`/api/book/${id}/bookmarks`, { method: 'POST', body: JSON.stringify(bm) }),
  delBookmark: (id, bid) => request(`/api/book/${id}/bookmarks/delete`, { method: 'POST', body: JSON.stringify({ id: bid }) }),
  search: (id, q, mode) => request(`/api/book/${id}/search?q=${encodeURIComponent(q)}&mode=${encodeURIComponent(mode || 'none')}`),
};

// pywebview 原生桥（对话框 / 窗口控制 / 外链）
export function bridge(fn, ...args) {
  const p = window.pywebview && window.pywebview.api;
  if (!p || typeof p[fn] !== 'function') return Promise.reject(new Error('原生桥未就绪'));
  try {
    return Promise.resolve(p[fn](...args));
  } catch (e) {
    return Promise.reject(e);
  }
}

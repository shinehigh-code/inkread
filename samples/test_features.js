// 新功能验证：滚轮翻页 + 语音朗读（真实引擎，headed）
const { chromium } = require('playwright');

(async () => {
  const base = `http://127.0.0.1:${process.argv[2]}`;
  const lib = await (await fetch(base + '/api/library')).json();
  const novel = lib.books.find((b) => b.title.includes('全本'));
  const comic = lib.books.find((b) => b.fmt === 'cbz');

  const browser = await chromium.launch({ channel: 'msedge', headless: false, args: ['--no-proxy-server'] });
  const page = await browser.newPage({ viewport: { width: 1160, height: 740 } });
  const errs = [];
  page.on('pageerror', (e) => errs.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  const ok = (n, c, extra = '') => console.log((c ? 'PASS ' : 'FAIL ') + n + (c ? '' : '  | ' + extra));

  // 前置：确保是翻页模式、单页漫画（避免上一轮测试残留的设置干扰）
  const setSettings = async (patch) => {
    await fetch(base + '/api/settings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch),
    });
    await page.reload(); // 只改 hash 不会重载页面，必须强制刷新才能让前端重新拉设置
    await page.waitForTimeout(400);
  };
  await setSettings({ mode: 'page', comic: { fit: 'fit-height', spread: 'single', dir: 'ltr' } });

  await page.goto(`${base}/#/read/${novel.id}`);
  await page.waitForSelector('.flow p');
  await page.waitForTimeout(500);

  // ---------- 1. 滚轮翻页（文本）
  await page.click('[data-act="toc"]');
  await page.click('.toc-item[data-i="1"]');
  await page.waitForTimeout(900);
  const p0 = await page.textContent('#pglabel');
  await page.mouse.move(580, 400);
  await page.mouse.wheel(0, 150);
  await page.waitForTimeout(700);
  const p1 = await page.textContent('#pglabel');
  ok('滚轮向下翻页', p0 !== p1, `${p0} -> ${p1}`);
  await page.mouse.wheel(0, -150);
  await page.waitForTimeout(700);
  const p2 = await page.textContent('#pglabel');
  ok('滚轮向上翻页', p2 !== p1, `${p1} -> ${p2}`);

  // ---------- 2. 语音列表（真实引擎）
  await page.click('[data-act="font"]');
  await page.waitForTimeout(300);
  const voices = await page.evaluate(() => [...document.querySelectorAll('#t-voice option')].map((o) => o.textContent));
  ok('语音列表（中文优先）', voices.length >= 1 && /慧慧|康康|瑶瑶/.test(voices[0]), JSON.stringify(voices));
  await page.click('[data-act="font"]');

  // ---------- 3. 朗读
  await page.click('[data-act="tts"]');
  await page.waitForTimeout(2500);
  const diag = await page.evaluate(() => {
    const rd = document.getElementById('reader');
    const hint = document.getElementById('tts-hint');
    return {
      supported: typeof window.speechSynthesis !== 'undefined',
      voiceCount: (window.speechSynthesis && window.speechSynthesis.getVoices().length) || 0,
      hint: hint ? hint.textContent.slice(0, 60) : '',
      stop: (rd && rd.dataset.ttsStop) || '',
      flowChildren: document.getElementById('flow') ? document.getElementById('flow').children.length : -1,
      speaker: !!window.__speakerDbg,
    };
  });
  console.log('      诊断:', JSON.stringify(diag));
  const r1 = await page.evaluate(() => ({
    bar: !document.getElementById('ttsbar').hidden,
    spans: document.querySelectorAll('.tts-s').length,
    hl: document.querySelectorAll('.tts-on').length,
    speaking: window.speechSynthesis.speaking,
    prog: document.getElementById('ttsprog').textContent,
    btn: document.querySelector('[data-act="tts"]').classList.contains('on'),
  }));
  ok('朗读条显示', r1.bar === true, JSON.stringify(r1));
  ok('按钮进入朗读态', r1.btn === true);
  ok('句子已切分', r1.spans > 3, String(r1.spans));
  ok('当前句高亮且唯一', r1.hl === 1, String(r1.hl));
  ok('引擎正在发声', r1.speaking === true, String(r1.speaking));
  ok('进度文案', /正在朗读 \d+ \/ \d+/.test(r1.prog), r1.prog);

  const follow = await page.evaluate(() => {
    const on = document.querySelector('.tts-on');
    const pv = document.getElementById('pv').getBoundingClientRect();
    if (!on) return { ok: false, top: -1, pvTop: -1 };
    const r = on.getBoundingClientRect();
    return { ok: r.top >= pv.top - 6 && r.bottom <= pv.bottom + 6, top: Math.round(r.top), pvTop: Math.round(pv.top) };
  });
  ok('高亮句在可视区内（自动跟随）', follow.ok === true, JSON.stringify(follow));
  if (!r1.bar) {
    console.log('\n页面错误:', errs.length ? errs : '(无)');
    await browser.close();
    return;
  }

  // 观察若干秒：朗读应持续推进，且不该中途停止
  const startProg = r1.prog;
  let moved = false;
  const trace = [];
  for (let i = 0; i < 14; i++) {
    await page.waitForTimeout(600);
    const s = await page.evaluate(() => {
      const rd = document.getElementById('reader');
      return {
        prog: document.getElementById('ttsprog') ? document.getElementById('ttsprog').textContent : '-',
        bar: document.getElementById('ttsbar') ? !document.getElementById('ttsbar').hidden : false,
        stop: (rd && rd.dataset.ttsStop) || '',
        speaking: window.speechSynthesis.speaking,
      };
    });
    trace.push(`${i}s:${s.prog}${s.bar ? '' : '(条已隐藏)'}${s.stop ? ' stop=' + s.stop : ''}${s.speaking ? '' : ' 静音'}`);
    if (s.prog !== startProg && !moved) moved = true;
    if (!s.bar) break;
  }
  console.log('      轨迹:', trace.join(' | '));
  ok('朗读持续推进且不中断', moved, startProg);

  // 暂停 / 继续
  await page.click('[data-act="tts-toggle"]');
  await page.waitForTimeout(800);
  const r2 = await page.evaluate(() => ({
    paused: document.querySelector('.tts-bar').classList.contains('paused'),
    speaking: window.speechSynthesis.speaking,
    pausedFlag: window.speechSynthesis.paused,
  }));
  ok('暂停生效', r2.paused === true && (r2.speaking === false || r2.pausedFlag === true), JSON.stringify(r2));
  await page.click('[data-act="tts-toggle"]');
  await page.waitForTimeout(1500);
  const r2b = await page.evaluate(() => ({
    paused: document.querySelector('.tts-bar').classList.contains('paused'),
    speaking: window.speechSynthesis.speaking,
  }));
  ok('继续生效', r2b.paused === false && r2b.speaking === true, JSON.stringify(r2b));

  // 停止
  await page.click('[data-act="tts-stop"]');
  await page.waitForTimeout(500);
  const r3 = await page.evaluate(() => ({
    bar: document.getElementById('ttsbar').hidden,
    spans: document.querySelectorAll('.tts-s').length,
    hl: document.querySelectorAll('.tts-on').length,
    speaking: window.speechSynthesis.speaking,
    btn: document.querySelector('[data-act="tts"]').classList.contains('on'),
  }));
  ok('停止后收起朗读条', r3.bar === true && r3.btn === false, JSON.stringify(r3));
  ok('停止后还原文本', r3.spans === 0 && r3.hl === 0, JSON.stringify(r3));
  ok('停止后不再发声', r3.speaking === false, String(r3.speaking));

  // ---------- 5. 滚动模式：滚轮必须能滚
  await setSettings({ mode: 'scroll' });
  await page.goto(`${base}/#/read/${novel.id}`);
  await page.waitForSelector('.flow p');
  await page.click('[data-act="toc"]');
  await page.click('.toc-item[data-i="1"]');
  await page.waitForTimeout(900);
  const s0 = await page.evaluate(() => document.getElementById('pv').scrollTop);
  await page.mouse.move(580, 400);
  await page.mouse.wheel(0, 400);
  await page.waitForTimeout(500);
  const s1 = await page.evaluate(() => document.getElementById('pv').scrollTop);
  ok('滚动模式滚轮可滚动', s1 > s0 + 40, `${s0} -> ${s1}`);

  // ---------- 6. 设置面板与沉浸模式互斥
  await setSettings({ mode: 'page' });
  await page.goto(`${base}/#/read/${novel.id}`);
  await page.waitForSelector('.flow p');
  await page.click('[data-act="font"]');
  await page.waitForTimeout(350);
  const before = await page.evaluate(() => ({
    pop: getComputedStyle(document.getElementById('pop')).display,
    imm: document.getElementById('reader').classList.contains('immersive'),
  }));
  await page.mouse.click(560, 420);
  await page.waitForTimeout(400);
  const after = await page.evaluate(() => ({
    pop: getComputedStyle(document.getElementById('pop')).display,
    imm: document.getElementById('reader').classList.contains('immersive'),
    barOpacity: getComputedStyle(document.querySelector('.r-bar')).opacity,
  }));
  ok('点正文只收起设置面板', before.pop === 'block' && after.pop === 'none', JSON.stringify({ before, after }));
  ok('收起面板后工具栏仍在', after.imm === false && after.barOpacity === '1', JSON.stringify(after));
  // 无面板时点正文应进入沉浸（用合成点击，避免测试工具的 mousemove 触发"动一下就显示工具栏"）
  await page.evaluate(() => document.querySelector('.zone.c').click());
  await page.waitForTimeout(400);
  const after2 = await page.evaluate(() => document.getElementById('reader').classList.contains('immersive'));
  ok('无面板时点正文进入沉浸', after2 === true, String(after2));

  await page.click('[data-act="font"]');
  await page.waitForTimeout(250);
  await page.click('.pop-head [data-act="font"]');
  await page.waitForTimeout(300);
  const closed = await page.evaluate(() => getComputedStyle(document.getElementById('pop')).display);
  ok('面板自带关闭按钮可用', closed === 'none', closed);

  // ---------- 7. 漫画滚轮
  await setSettings({ comic: { fit: 'fit-height', spread: 'single', dir: 'ltr' } });
  await page.goto(`${base}/#/read/${comic.id}`);
  await page.waitForSelector('.cpage');
  const c0 = await page.textContent('#pglabel');
  await page.mouse.move(580, 400);
  await page.mouse.wheel(0, 150);
  await page.waitForTimeout(500);
  const c1 = await page.textContent('#pglabel');
  ok('漫画滚轮翻页', c0 !== c1, `${c0} -> ${c1}`);

  console.log('\n页面错误:', errs.length ? errs.slice(0, 5) : '(无)');
  await browser.close();
})();

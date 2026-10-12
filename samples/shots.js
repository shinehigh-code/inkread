// 界面巡检：逐屏截图，收集控制台错误
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const port = process.argv[2];
  const base = `http://127.0.0.1:${port}`;
  const out = path.join(__dirname, '..', 'shots');
  fs.mkdirSync(out, { recursive: true });

  const lib = await (await fetch(base + '/api/library')).json();
  const by = (needle, fmt) => lib.books.find((b) => b.title.includes(needle) && (!fmt || b.fmt === fmt));

  const browser = await chromium.launch({ channel: 'msedge', args: ['--no-proxy-server'] });
  const page = await browser.newPage({ viewport: { width: 1340, height: 880 }, deviceScaleFactor: 1.25 });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message));

  const shot = async (name) => {
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(out, name + '.png') });
    console.log('shot', name);
  };

  await page.goto(base);
  await page.waitForSelector('.book', { timeout: 15000 });
  await shot('01-library-grid');

  await page.click('#liblayout button[data-v="list"]');
  await shot('02-library-list');
  await page.click('#liblayout button[data-v="grid"]');

  // 文本阅读器
  const txt = by('雾港往事', 'txt');
  await page.goto(`${base}/#/read/${txt.id}`);
  await page.waitForSelector('.flow p', { timeout: 15000 });
  await shot('03-reader-txt');

  // 分页诊断 + 翻到第二页确认不被裁切
  console.log('pagination', JSON.stringify(await page.evaluate(() => {
    const flow = document.getElementById('flow');
    const cs = getComputedStyle(flow);
    const label = document.getElementById('pglabel');
    return {
      colW: cs.columnWidth, gap: cs.columnGap, fill: cs.columnFill,
      scrollW: flow.scrollWidth, clientW: flow.clientWidth,
      padL: cs.paddingLeft, padR: cs.paddingRight,
      pages: label ? label.textContent : '', transform: flow.style.transform,
    };
  })));
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ArrowRight');
  await shot('03b-reader-page3');
  console.log('page3', await page.textContent('#pglabel'));
  await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('ArrowLeft');

  await page.click('[data-act="font"]');
  await shot('04-reader-settings');
  await page.click('[data-act="font"]');

  await page.click('[data-act="toc"]');
  await shot('05-reader-toc');
  await page.click('[data-act="close-toc"]');

  await page.click('[data-act="search"]');
  await page.fill('#srinput', '航标灯');
  await page.press('#srinput', 'Enter');
  await page.waitForTimeout(700);
  await shot('06-reader-search');
  await page.click('[data-act="close-rd"]');

  // Markdown + KaTeX
  const md = by('无线传感器');
  await page.goto(`${base}/#/read/${md.id}`);
  await page.waitForSelector('.katex', { timeout: 15000 });
  await shot('07-reader-md-math');

  // EPUB
  const epub = by('雾港往事', 'epub');
  await page.goto(`${base}/#/read/${epub.id}`);
  await page.waitForSelector('.flow img', { timeout: 15000 });
  await shot('08-reader-epub');

  // 漫画
  const comic = by('comic', 'cbz');
  await page.goto(`${base}/#/read/${comic.id}`);
  await page.waitForSelector('.cpage', { timeout: 15000 });
  await shot('09-comic-single');
  await page.click('[data-act="spread"]');
  await shot('10-comic-double');
  await page.click('[data-act="spread"]');
  await page.click('[data-act="fit"]');
  await page.click('[data-act="fit"]');
  await page.click('[data-act="fit"]');
  await shot('11-comic-continuous');

  // 深色主题下的阅读器
  await page.goto(`${base}/#/read/${txt.id}`);
  await page.waitForSelector('.flow p', { timeout: 15000 });
  await page.click('[data-act="font"]');
  await page.click('.swatch[data-t="ink"]');
  await shot('12-reader-dark');
  await page.click('[data-act="font"]');

  // 设置页
  await page.goto(`${base}/#/settings`);
  await shot('13-settings');
  await page.click('.swatch[data-t="paper"]');

  console.log('\n=== console errors ===');
  console.log(errors.length ? errors.join('\n') : '(none)');
  await browser.close();
})();

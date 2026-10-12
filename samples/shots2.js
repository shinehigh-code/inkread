// 最终巡检：覆盖全部视图与交互状态，输出到 shots/final
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const port = process.argv[2];
  const base = `http://127.0.0.1:${port}`;
  const out = path.join(__dirname, '..', 'shots', 'final');
  fs.mkdirSync(out, { recursive: true });

  const lib = await (await fetch(base + '/api/library')).json();
  const find = (t, fmt) => lib.books.find((b) => b.title.includes(t) && (!fmt || b.fmt === fmt));

  const browser = await chromium.launch({ channel: 'msedge', args: ['--no-proxy-server'] });
  const page = await browser.newPage({ viewport: { width: 1340, height: 880 }, deviceScaleFactor: 1.25 });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message));
  const shot = async (n) => { await page.waitForTimeout(450); await page.screenshot({ path: path.join(out, n + '.png') }); console.log('shot', n); };

  // 弹层/抽屉显式开关，避免依赖上一步状态
  const popVisible = () => page.evaluate(() => {
    const p = document.getElementById('pop');
    return !!p && getComputedStyle(p).display !== 'none';
  });
  const openPop = async () => { if (!(await popVisible())) await page.click('[data-act="font"]'); };
  const closePop = async () => { if (await popVisible()) await page.click('[data-act="font"]'); };
  const closeDrawers = () => page.evaluate(() => {
    document.getElementById('toc-drawer').classList.remove('open');
    document.getElementById('right-drawer').classList.remove('open');
  });
  const setTheme = async (t) => { await openPop(); await page.click(`.swatch[data-t="${t}"]`); await closePop(); };

  const novel = find('雾港往事（全本）');
  const md = find('无线传感器');
  const epub = find('雾港往事', 'epub');
  const comic = find('comic', 'cbz');

  // 1. 长篇小说翻到第 2 页；回书库看「继续阅读」
  await page.goto(`${base}/#/read/${novel.id}`);
  await page.waitForSelector('.flow p');
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(800);
  await page.keyboard.press('ArrowRight');
  await shot('01-reader-page2');

  await page.goto(`${base}/#/library`);
  await page.waitForSelector('.book');
  await shot('02-library-continue');
  await page.click('#liblayout button[data-v="list"]');
  await shot('03-library-list');
  await page.click('#liblayout button[data-v="grid"]');

  // 2. 滚动模式
  await page.goto(`${base}/#/read/${novel.id}`);
  await page.waitForSelector('.flow p');
  await openPop();
  await page.click('#f-mode button[data-v="scroll"]');
  await page.waitForTimeout(800);
  await page.mouse.move(660, 500);
  await page.mouse.wheel(0, 1200);
  await shot('04-reader-scroll');

  // 3. 目录抽屉 + 茶色主题
  await closePop();
  await page.click('[data-act="toc"]');
  await shot('05-reader-toc');
  await closeDrawers();
  await setTheme('sepia');
  await shot('06-reader-sepia');

  // 4. 全文搜索 + 命中高亮
  await page.click('[data-act="search"]');
  await page.fill('#srinput', '雾散得很慢');
  await page.press('#srinput', 'Enter');
  await page.waitForTimeout(900);
  await shot('07-reader-search');
  await page.click('.sr-item');
  await page.waitForTimeout(1000);
  await shot('08-reader-highlight');

  // 5. 书签
  await closeDrawers();
  await page.click('[data-act="bookmark"]');
  await page.waitForTimeout(900);
  await shot('09-reader-bookmarks');
  await closeDrawers();
  await setTheme('paper');

  // 6. Markdown（含公式）/ EPUB
  await page.goto(`${base}/#/read/${md.id}`);
  await page.waitForSelector('.katex');
  await shot('10-md-math');
  await page.goto(`${base}/#/read/${epub.id}`);
  await page.waitForSelector('.flow img');
  await shot('11-epub');

  // 7. 漫画：双页配对 → 右到左 → 连续滚动
  await fetch(base + '/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ comic: { fit: 'fit-height', spread: 'single', dir: 'ltr' } }),
  });
  await page.goto(`${base}/#/read/${comic.id}`);
  await page.waitForSelector('.cpage');
  await page.click('.r-bar.btm [data-act="spread"]');
  await page.click('.r-bar.btm [data-act="next"]');
  await page.waitForTimeout(800);
  await shot('12-comic-double-pair');
  await page.click('.r-bar.btm [data-act="dir"]');
  await page.waitForTimeout(600);
  await shot('13-comic-rtl');
  for (let i = 0; i < 3; i++) await page.click('.r-bar.btm [data-act="fit"]');
  await page.waitForTimeout(900);
  await shot('14-comic-continuous');
  await fetch(base + '/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ comic: { fit: 'fit-height', spread: 'single', dir: 'ltr' } }),
  });

  // 8. 深色主题 + 设置页
  await page.goto(`${base}/#/read/${novel.id}`);
  await page.waitForSelector('.flow p');
  await setTheme('ink');
  await shot('15-reader-dark');
  await page.goto(`${base}/#/settings`);
  await shot('16-settings');
  await setTheme('paper');

  console.log('\n=== console errors ===');
  console.log(errors.length ? errors.join('\n') : '(none)');
  await browser.close();
})();

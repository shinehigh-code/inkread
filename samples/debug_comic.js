// 漫画翻页状态一致性检查
const { chromium } = require('playwright');

(async () => {
  const base = 'http://127.0.0.1:' + process.argv[2];
  const lib = await (await fetch(base + '/api/library')).json();
  const comic = lib.books.find((b) => b.fmt === 'cbz');
  const get = (u) => fetch(base + u).then((r) => r.json());
  const post = (u, body) => fetch(base + u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then((r) => r.json());

  await post('/api/settings', { comic: { fit: 'fit-height', spread: 'single', dir: 'ltr' } });
  await post(`/api/book/${comic.id}/progress`, { chapter: 0, page: 0, scroll: 0, pct: 0 });

  const browser = await chromium.launch({ channel: 'msedge', args: ['--no-proxy-server'] });
  const page = await browser.newPage({ viewport: { width: 1340, height: 880 } });
  await page.goto(`${base}/#/read/${comic.id}`);
  await page.waitForSelector('.cpage');

  const probe = async (tag) => {
    const info = await page.evaluate(() => ({
      label: document.getElementById('pglabel').textContent,
      slider: document.getElementById('pgsld').value,
      imgs: [...document.querySelectorAll('.cpage')].map((i) => i.src.split('/').pop()),
      stage: document.getElementById('stage').className,
    }));
    console.log(tag, JSON.stringify(info));
  };

  await probe('初始(单页,第1页)');
  await page.click('.r-bar.btm [data-act="spread"]');
  await page.waitForTimeout(400);
  await probe('切双页(page0)');
  await page.click('.r-bar.btm [data-act="next"]');
  await page.waitForTimeout(600);
  await probe('下一页');
  await page.click('.r-bar.btm [data-act="next"]');
  await page.waitForTimeout(600);
  await probe('再下一页');
  await page.click('.r-bar.btm [data-act="dir"]');
  await page.waitForTimeout(500);
  await probe('右到左');
  await page.click('.r-bar.btm [data-act="prev"]');
  await page.waitForTimeout(600);
  await probe('右到左-上一页');
  await probe('保存的进度');
  const prog = await get(`/api/book/${comic.id}`);
  console.log('服务端进度:', JSON.stringify(prog.progress));
  await browser.close();
})();
